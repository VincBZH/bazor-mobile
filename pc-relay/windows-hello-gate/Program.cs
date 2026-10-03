// Proof component for the EXISTING BAZOR Hub: local UI + genuine Windows Hello.
// It does not start a second BAZOR, run scripts, write files, or accept remote commands.
// Production IPC/signature enforcement must be implemented and validated separately.
using Microsoft.Win32;
using System.Net;
using System.Windows.Forms;
using Windows.Security.Credentials.UI;

namespace BazorHelloGate;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new HelloForm());
    }
}

internal sealed class HelloForm : Form
{
    private readonly Button _enable = new()
    {
        Text = "Autoriser les diagnostics (Windows Hello)",
        Width = 390, Height = 48, Left = 16, Top = 72
    };
    private readonly Button _check = new()
    {
        Text = "Vérifier Core / Room / Ollama",
        Width = 390, Height = 44, Left = 16, Top = 132, Enabled = false
    };
    private readonly Button _panic = new()
    {
        Text = "PANIC — retirer immédiatement l'autorisation",
        Width = 390, Height = 45, Left = 16, Top = 188
    };
    private readonly Label _status = new()
    {
        Text = "DÉSACTIVÉ — aucune action n'est autorisée.",
        AutoSize = false, Width = 392, Height = 48, Left = 16, Top = 16
    };
    private readonly System.Windows.Forms.Timer _expiry = new() { Interval = 1000 };
    private readonly HttpClient _http = new(new SocketsHttpHandler
    {
        UseProxy = false, AllowAutoRedirect = false, ConnectTimeout = TimeSpan.FromSeconds(2)
    })
    {
        Timeout = TimeSpan.FromSeconds(4)
    };
    private DateTimeOffset _until = DateTimeOffset.MinValue;
    private int _epoch;

    public HelloForm()
    {
        Text = "BAZOR — autorisation locale (prototype)";
        Width = 440;
        Height = 294;
        MaximizeBox = false;
        FormBorderStyle = FormBorderStyle.FixedDialog;
        Controls.AddRange(new Control[] { _enable, _check, _panic, _status });
        _enable.Click += async (_, _) => await RequestAuthorizationAsync();
        _check.Click += async (_, _) => await InspectAsync();
        _panic.Click += (_, _) => Revoke("PANIC : autorisation supprimée.");
        _expiry.Tick += (_, _) =>
        {
            if (DateTimeOffset.UtcNow >= _until && _check.Enabled)
                Revoke("Autorisation expirée. Vérifie-toi à nouveau.");
        };
        _expiry.Start();
        SystemEvents.SessionSwitch += SessionChanged;
        FormClosed += (_, _) =>
        {
            Revoke("Fermeture");
            SystemEvents.SessionSwitch -= SessionChanged;
            _http.Dispose();
            _expiry.Dispose();
        };
    }

    private void SessionChanged(object sender, SessionSwitchEventArgs args)
    {
        if (args.Reason is SessionSwitchReason.SessionLock
            or SessionSwitchReason.SessionLogoff
            or SessionSwitchReason.ConsoleDisconnect
            or SessionSwitchReason.RemoteDisconnect)
        {
            // Invalidate immediately even when the UI event is not on the UI thread.
            Interlocked.Increment(ref _epoch);
            _until = DateTimeOffset.MinValue;
            if (IsHandleCreated)
                BeginInvoke(new Action(() => Revoke("Windows verrouillé : autorisation révoquée.")));
        }
    }

    private bool HasPermission(int epoch)
        => epoch == Volatile.Read(ref _epoch)
           && _check.Enabled
           && DateTimeOffset.UtcNow < _until;

    private void Revoke(string message)
    {
        Interlocked.Increment(ref _epoch);
        _until = DateTimeOffset.MinValue;
        _check.Enabled = false;
        _enable.Enabled = true;
        _status.Text = message;
    }

    private async Task RequestAuthorizationAsync()
    {
        // No PIN/password ever leaves the native Windows prompt.
        Revoke("Vérification Windows Hello…");
        var attempt = Volatile.Read(ref _epoch);
        _enable.Enabled = false;
        try
        {
            var availability = await UserConsentVerifier.CheckAvailabilityAsync();
            if (availability != UserConsentVerifierAvailability.Available)
            {
                Revoke("Windows Hello indisponible ou non configuré.");
                return;
            }
            var consent = await UserConsentVerifierInterop.RequestVerificationForWindowAsync(
                Handle, "Autoriser BAZOR à vérifier les services locaux pendant 15 minutes ?");
            if (attempt != Volatile.Read(ref _epoch))
                return; // PANIC or Windows lock happened during Hello prompt.
            if (consent != UserConsentVerificationResult.Verified)
            {
                Revoke("Vérification refusée ou annulée.");
                return;
            }
            _until = DateTimeOffset.UtcNow.AddMinutes(15);
            _check.Enabled = true;
            _status.Text = "AUTORISÉ 15 MIN — diagnostics locaux uniquement. Aucun déploiement.";
        }
        catch (Exception)
        {
            // An unavailable WinRT API or other error always fails closed.
            Revoke("Vérification impossible : aucune autorisation accordée.");
        }
        finally
        {
            _enable.Enabled = true;
        }
    }

    private async Task InspectAsync()
    {
        var epoch = Volatile.Read(ref _epoch);
        if (!HasPermission(epoch))
        {
            Revoke("Session expirée, verrouillée ou désactivée.");
            return;
        }
        _check.Enabled = false;
        try
        {
            string[] endpoints = {
                "http://127.0.0.1:8775/api/v1/health",
                "http://127.0.0.1:8765/api/status",
                "http://127.0.0.1:11434/api/tags"
            };
            int responding = 0;
            foreach (var endpoint in endpoints)
            {
                if (epoch != Volatile.Read(ref _epoch) || DateTimeOffset.UtcNow >= _until)
                    return;
                try
                {
                    using var request = new HttpRequestMessage(HttpMethod.Get, endpoint);
                    using var reply = await _http.SendAsync(request,
                        HttpCompletionOption.ResponseHeadersRead);
                    if (reply.StatusCode == HttpStatusCode.OK)
                        responding++;
                }
                catch (HttpRequestException) { }
                catch (TaskCanceledException) { }
            }
            if (epoch == Volatile.Read(ref _epoch) && DateTimeOffset.UtcNow < _until)
                _status.Text = $"{responding}/3 services joignables (HTTP seulement ; identité non certifiée).";
        }
        finally
        {
            _check.Enabled = epoch == Volatile.Read(ref _epoch)
                             && DateTimeOffset.UtcNow < _until;
        }
    }
}
