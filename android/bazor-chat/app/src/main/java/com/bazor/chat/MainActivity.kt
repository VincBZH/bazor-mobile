package com.bazor.chat

import android.app.Activity
import android.app.ActivityManager
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.*
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import com.arm.aichat.InferenceEngine.State
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.collect
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

class MainActivity : ComponentActivity() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private lateinit var engine: InferenceEngine
    private lateinit var transcript: TextView
    private lateinit var status: TextView
    private lateinit var input: EditText
    private lateinit var modelLabel: TextView
    private lateinit var mode: Spinner
    private lateinit var selectedAgent: Spinner
    private lateinit var turnLimit: SeekBar
    private var turns = 4
    private var modelFile: File? = null
    private var generation: Job? = null
    private var downloadJob: Job? = null
    @Volatile private var activeDownloadConnection: HttpURLConnection? = null
    private lateinit var downloadButton: Button
    private val history = mutableListOf<Pair<String, String>>()
    private val pickModel = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) importModel(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(15, 18, 24)
        window.navigationBarColor = Color.rgb(15, 18, 24)
        engine = AiChat.getInferenceEngine(applicationContext)
        buildUi()
        restoreHistory()
        val saved = File(filesDir, "model.gguf")
        if (saved.exists()) { modelFile = saved; modelLabel.text = "Modèle : ${saved.name} • ${formatSize(saved.length())}" }
    }

    private fun buildUi() {
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(16, 16, 16, 12); setBackgroundColor(Color.rgb(15,18,24)) }
        root.addView(TextView(this).apply { text = "BAZOR CHAT  •  V1.0.0\nDeux agents, un modèle local"; textSize = 21f; setTextColor(Color.WHITE) })
        modelLabel = TextView(this).apply { text = "Aucun modèle local chargé"; setTextColor(0xffbdc8d6.toInt()); setPadding(0,12,0,6) }
        root.addView(modelLabel)
        val modelButtons = LinearLayout(this)
        modelButtons.addView(button("Choisir un fichier GGUF") { pickModel.launch(arrayOf("application/octet-stream", "*/*")) }, weighted())
        modelButtons.addView(button("Charger") { loadModel() }, weighted())
        modelButtons.addView(button("Décharger") { unloadModel() }, weighted())
        root.addView(modelButtons)
        val downloadRow = LinearLayout(this)
        downloadButton = button("Télécharger Qwen 1.5B Q4 • ~986 Mo • Apache-2.0") { downloadModel() }
        downloadRow.addView(downloadButton, weighted())
        downloadRow.addView(button("Annuler téléchargement") { downloadJob?.cancel(); activeDownloadConnection?.disconnect() }, weighted())
        root.addView(downloadRow)
        mode = Spinner(this).apply { adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, listOf("Automatique", "Débat", "Collaboration", "Manuel")) }
        root.addView(mode)
        selectedAgent = Spinner(this).apply { adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item, listOf("IA A", "IA B", "Les deux")) }
        root.addView(selectedAgent)
        val turnRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL }
        turnRow.addView(TextView(this).apply { text = "Tours max :"; setTextColor(Color.WHITE) })
        turnLimit = SeekBar(this).apply { max = 18; progress = 2; setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) { turns = progress + 2 }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        }) }
        turnRow.addView(turnLimit, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        turnRow.addView(TextView(this).apply { setTextColor(Color.WHITE); text = "4"; turns = 4; turnLimit.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) { turns = progress + 2; text = turns.toString() }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        }) })
        root.addView(turnRow)
        status = TextView(this).apply { text = "Local uniquement • Choisissez un fichier modèle GGUF"; setTextColor(0xff89c2ff.toInt()); setPadding(0,6,0,8) }
        root.addView(status)
        val scroll = ScrollView(this)
        transcript = TextView(this).apply { textSize = 15f; setTextColor(Color.WHITE); setPadding(4,8,4,8); text = "Bienvenue. Les réponses ne sont pas simulées : un modèle GGUF chargé est nécessaire." }
        scroll.addView(transcript)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        input = EditText(this).apply { hint = "Écrire un message…"; setTextColor(Color.WHITE); setHintTextColor(0xff8b96a5.toInt()); setSingleLine(false); minLines = 2 }
        root.addView(input)
        val actions = LinearLayout(this).apply { gravity = Gravity.CENTER }
        actions.addView(button("Envoyer") { send() }, weighted())
        actions.addView(button("STOP") { stopGeneration() }, weighted())
        actions.addView(button("Effacer") { history.clear(); saveHistory(); renderHistory() }, weighted())
        root.addView(actions)
        setContentView(root)
    }

    private fun weighted() = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
    private fun button(label: String, action: () -> Unit) = Button(this).apply { text = label; setOnClickListener { action() } }

    private fun importModel(uri: Uri) {
        if (generation?.isActive == true) { status.text = "Arrêtez d'abord la génération en cours."; return }
        status.text = "Copie du modèle dans le stockage privé…"
        scope.launch(Dispatchers.IO) {
            try {
                if (engine.state.value is State.ModelReady) engine.cleanUp()
                val dest = File(filesDir, "model.gguf")
                contentResolver.openInputStream(uri).use { src ->
                    val inputStream = requireNotNull(src) { "Fichier inaccessible" }
                    dest.outputStream().buffered().use { outputStream -> inputStream.copyTo(outputStream) }
                }
                require(dest.length() >= 1024 * 1024) { "Fichier trop petit pour être un modèle GGUF" }
                val header = dest.inputStream().use { ByteArray(4).also { b -> require(it.read(b) == 4) } }
                require(String(header) == "GGUF") { "Ce fichier n'a pas un en-tête GGUF valide" }
                withContext(Dispatchers.Main) { modelFile = dest; modelLabel.text = "${dest.name} • ${formatSize(dest.length())} • stockage privé"; status.text = "Fichier vérifié (en-tête GGUF). Chargement disponible." }
            } catch (e: Exception) { withContext(Dispatchers.Main) { status.text = "Import refusé : ${e.message}" } }
        }
    }

    private fun loadModel() {
        val file = modelFile ?: run { status.text = "Choisissez d'abord un fichier GGUF."; return }
        if (engine.state.value is State.ModelReady) { status.text = "Le modèle est déjà chargé."; return }
        val am = getSystemService(Activity.ACTIVITY_SERVICE) as ActivityManager
        val memory = ActivityManager.MemoryInfo().also(am::getMemoryInfo)
        if (memory.availMem < 1_500L * 1024 * 1024) { status.text = "RAM disponible trop basse (< 1,5 Go). Fermez des applications puis réessayez."; return }
        status.text = "Chargement local… Un modèle peut prendre plusieurs minutes."
        scope.launch(Dispatchers.IO) {
            try {
                engine.loadModel(file.absolutePath)
                withContext(Dispatchers.Main) { status.text = "Modèle local chargé • ${formatSize(file.length())} • hors connexion" }
            } catch (e: Exception) { withContext(Dispatchers.Main) { status.text = "Échec du chargement : ${e.message}" } }
        }
    }

    private fun unloadModel() {
        if (generation?.isActive == true) { status.text = "Arrêtez la génération avant de décharger le modèle."; return }
        scope.launch(Dispatchers.IO) {
            try {
                engine.cleanUp()
                withContext(Dispatchers.Main) { status.text = "Modèle déchargé de la mémoire. Le fichier reste dans le stockage privé." }
            } catch (e: Exception) { withContext(Dispatchers.Main) { status.text = "Déchargement impossible : ${e.message}" } }
        }
    }

    private fun downloadModel() {
        if (downloadJob?.isActive == true) return
        if (generation?.isActive == true) { status.text = "Arrêtez d'abord la génération en cours."; return }
        val modelUrl = "https://huggingface.co/second-state/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"
        val temp = File(filesDir, "model.gguf.part")
        val dest = File(filesDir, "model.gguf")
        downloadButton.isEnabled = false
        status.text = "Téléchargement choisi par vous • modèle ~986 Mo • les réponses resteront locales"
        downloadJob = scope.launch(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                if (engine.state.value is State.ModelReady) engine.cleanUp()
                val metadata = (URL(modelUrl).openConnection() as HttpURLConnection).apply {
                    activeDownloadConnection = this
                    requestMethod = "HEAD"; connectTimeout = 20_000; readTimeout = 20_000; instanceFollowRedirects = false; connect()
                }
                val expectedHash = metadata.getHeaderField("X-Linked-Etag")?.trim('"')?.lowercase()
                val expectedBytes = metadata.getHeaderFieldLong("X-Linked-Size", -1L)
                val location = metadata.getHeaderField("Location")
                metadata.disconnect()
                activeDownloadConnection = null
                require(expectedHash?.matches(Regex("[0-9a-f]{64}")) == true) { "Le serveur n'a pas fourni de SHA-256 vérifiable. Aucun modèle installé." }
                require(location != null) { "Le dépôt n'a pas fourni de lien de téléchargement." }
                require(expectedBytes in 900_000_000L..1_200_000_000L) { "Taille du modèle inattendue (${expectedBytes} octets). Téléchargement refusé." }
                connection = (URL(location).openConnection() as HttpURLConnection).apply {
                    activeDownloadConnection = this
                    connectTimeout = 30_000; readTimeout = 60_000; connect()
                }
                require(connection!!.responseCode == 200) { "Téléchargement HTTP ${connection!!.responseCode}" }
                require(filesDir.usableSpace > expectedBytes + 300_000_000L) { "Espace libre insuffisant. Libérez au moins ${formatSize(expectedBytes + 300_000_000L)}." }
                val digest = MessageDigest.getInstance("SHA-256")
                var total = 0L
                connection!!.inputStream.use { source -> temp.outputStream().buffered().use { sink ->
                    val buffer = ByteArray(256 * 1024)
                    while (true) {
                        ensureActive()
                        val count = source.read(buffer)
                        if (count < 0) break
                        sink.write(buffer, 0, count); digest.update(buffer, 0, count); total += count
                        if (total % (4L * 1024 * 1024) < buffer.size) withContext(Dispatchers.Main) {
                            status.text = "Téléchargement : ${formatSize(total)} / ${formatSize(expectedBytes)} (${(total * 100 / expectedBytes).coerceAtMost(100)} %)"
                        }
                    }
                } }
                val actualHash = digest.digest().joinToString("") { "%02x".format(it) }
                require(total == expectedBytes) { "Téléchargement incomplet : $total / $expectedBytes octets." }
                require(actualHash == expectedHash) { "Le SHA-256 du modèle ne correspond pas à la source." }
                require(temp.inputStream().use { input -> ByteArray(4).also { require(input.read(it) == 4) } }.let { String(it) == "GGUF" }) { "En-tête GGUF invalide." }
                check(temp.renameTo(dest)) { "Impossible d'installer le modèle dans le stockage privé." }
                withContext(Dispatchers.Main) {
                    modelFile = dest
                    modelLabel.text = "Qwen2.5 1.5B Q4_K_M • ${formatSize(dest.length())} • SHA-256 validé"
                    status.text = "Modèle téléchargé et vérifié. Touchez Charger pour initialiser l'inférence locale."
                }
            } catch (e: CancellationException) {
                temp.delete()
                withContext(NonCancellable + Dispatchers.Main) { status.text = "Téléchargement annulé. Fichier temporaire supprimé." }
                throw e
            } catch (e: Exception) {
                temp.delete()
                withContext(Dispatchers.Main) { status.text = "Téléchargement impossible : ${e.message}" }
            } finally {
                connection?.disconnect()
                activeDownloadConnection = null
                withContext(NonCancellable + Dispatchers.Main) { downloadButton.isEnabled = true }
            }
        }
    }

    private fun send() {
        if (generation?.isActive == true) return
        val prompt = input.text.toString().trim()
        if (prompt.isEmpty()) return
        if (!engine.state.value.let { it is State.ModelReady || it is State.Generating }) { status.text = "Chargez un modèle GGUF avant de discuter."; return }
        input.text.clear()
        history += "Vous" to prompt
        saveHistory(); renderHistory()
        val selected = mode.selectedItemPosition
        val choice = selectedAgent.selectedItemPosition
        val responders = when (selected) {
            0, 2 -> listOf("IA A", "IA B")
            1 -> List(turns) { if (it % 2 == 0) "IA A" else "IA B" }
            else -> when (choice) { 0 -> listOf("IA A"); 1 -> listOf("IA B"); else -> listOf("IA A", "IA B") }
        }
        val maxTurns = responders.size
        generation = scope.launch {
            try {
                for ((index, agent) in responders.withIndex()) {
                    if (!isActive) break
                    status.text = "$agent réfléchit… (${index + 1}/$maxTurns)"
                    val modePrompt = when (selected) {
                        1 -> "Débat : examine la réponse précédente et donne un argument distinct, sans répétitions."
                        2 -> "Collaboration : apporte une étape complémentaire et concrète au travail commun."
                        else -> ""
                    }
                    val instruction = when (agent) {
                        "IA A" -> "Tu es l'IA A de BAZOR CHAT. Propose des idées utiles, concises et constructives. $modePrompt Réponds toujours en français."
                        else -> "Tu es l'IA B de BAZOR CHAT. Analyse la demande et la contribution précédente de l'IA A. Complète ou corrige avec esprit critique, sans répéter. $modePrompt Réponds toujours en français."
                    }
                    engine.setSystemPrompt(instruction)
                    val answer = StringBuilder()
                    val contextualPrompt = if (index == 0) prompt else "Contexte de la demande initiale : $prompt. Contribution précédente : ${history.lastOrNull()?.second ?: "aucune"}"
                    engine.sendUserPrompt(contextualPrompt, predictLength = 256)
                        .collect { token -> answer.append(token); transcript.text = renderTextWithPending(agent, answer.toString()) }
                    history += agent to answer.toString().trim()
                    saveHistory(); renderHistory()
                }
                status.text = "Réponse terminée • traitement local"
            } catch (e: CancellationException) { status.text = "Génération interrompue."; throw e }
            catch (e: Exception) { status.text = "Erreur moteur : ${e.message}" }
        }
    }

    private fun renderTextWithPending(agent: String, pending: String) = buildString {
        history.forEach { (who, msg) -> append("$who\n$msg\n\n") }
        append("$agent\n$pending")
    }
    private fun stopGeneration() { generation?.cancel(); generation = null; status.text = "Arrêt demandé." }
    private fun renderHistory() { transcript.text = if (history.isEmpty()) "Nouvelle conversation locale." else history.joinToString("\n\n") { "${it.first}\n${it.second}" } }
    private fun saveHistory() { getSharedPreferences("chat", MODE_PRIVATE).edit().putString("history", JSONArray().also { a -> history.forEach { a.put(JSONObject().put("who", it.first).put("text", it.second)) } }.toString()).apply() }
    private fun restoreHistory() { try { val a = JSONArray(getSharedPreferences("chat", MODE_PRIVATE).getString("history", "[]")); for (i in 0 until a.length()) { val o = a.getJSONObject(i); history += o.getString("who") to o.getString("text") }; renderHistory() } catch (_: Exception) { history.clear() } }
    private fun formatSize(bytes: Long) = "%.2f Go".format(bytes / (1024.0 * 1024 * 1024))
    override fun onDestroy() { generation?.cancel(); scope.cancel(); super.onDestroy() }
}
