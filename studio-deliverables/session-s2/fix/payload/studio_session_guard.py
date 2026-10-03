"""Session S2: validate media bytes before sending them to Ollama."""
import asyncio
import io
from PIL import Image, ImageOps


def engine_error_summary(body):
    import json
    if not isinstance(body,dict):return str(body)[:600]
    messages=[]
    for node_id,node in (body.get('node_errors') or {}).items():
        for error in node.get('errors',[]):
            detail=error.get('details') or error.get('message') or 'entrée incompatible'
            kind=node.get('class_type') or node_id
            messages.append('Nœud '+str(kind)+' ('+str(node_id)+') : '+str(detail)[:400])
    if messages:
        return 'ComfyUI a refusé le workflow. '+ ' | '.join(messages[:3])+' — Détails complets dans le diagnostic.'
    error=body.get('error',body)
    if isinstance(error,str):
        try:return engine_error_summary(json.loads(error))
        except (ValueError,TypeError):return error[:600]
    if isinstance(error,dict):return str(error.get('message') or error.get('type') or json.dumps(error,ensure_ascii=False))[:600]
    return str(error)[:600]


def normalize_analysis_image(raw):
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 25_000_000:
                raise ValueError('Image trop grande pour le contrôle visuel.')
            image.seek(0)
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1024, 1024))
            rgba = image.convert('RGBA')
            canvas = Image.new('RGB', rgba.size, 'white')
            canvas.paste(rgba, mask=rgba.getchannel('A'))
            stream = io.BytesIO()
            canvas.save(stream, 'JPEG', quality=90)
            return stream.getvalue()
    except Exception as exc:
        raise ValueError('Le résultat reçu ne contient pas une image décodable. Aucune analyse envoyée.') from exc


async def select_vision_model(studio, requested, names):
    """Use model capabilities, never trust a model name as proof of vision."""
    ordered = sorted(names, key=lambda name: (name != requested, name))
    for name in ordered:
        try:
            description = await studio.request('POST', '/api/show', {'model': name},
                                               base=studio.ollama, timeout=20)
        except Exception:
            continue
        if 'vision' in (description.get('capabilities') or []):
            return name
    raise ValueError('Aucun modèle installé ne confirme la capacité vision. Vérifie Ollama et ses modèles ; aucune analyse fictive n’a été produite.')


async def read_media_limited(content, maximum=30*1024*1024):
    chunks = bytearray()
    async for chunk in content.iter_chunked(65536):
        chunks.extend(chunk)
        if len(chunks) > maximum:
            raise ValueError('Média trop volumineux pour une analyse locale.')
    if not chunks:
        raise ValueError('Le média reçu est vide.')
    return bytes(chunks)
