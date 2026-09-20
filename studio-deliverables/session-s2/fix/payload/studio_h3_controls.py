"""Bind geometry only to inputs declared by the graph or the live node schema."""
import copy

PAIRS = (('width', 'height'), ('video_width', 'video_height'), ('image_width', 'image_height'))
NATIVE = {'EmptyMiniMaxH3LatentAV', 'MiniMaxH3ImageToVideo', 'MiniMaxH3ReferenceToVideo'}


def unwrap_graph(value):
    for _ in range(8):
        if not isinstance(value, dict):
            break
        if any(isinstance(n, dict) and 'class_type' in n for n in value.values()):
            return value
        nested = next((value[k] for k in ('prompt', 'graph', 'api_prompt', 'output', 'data')
                       if isinstance(value.get(k), dict)), None)
        if nested is None:
            break
        value = nested
    raise ValueError('Workflow H3 non converti en graphe API : exporte le workflow au format API dans ComfyUI.')


def patch_controls(graph, p, prefix, info=None):
    # Build all changes on a copy; unknown geometry leaves the original intact.
    staged = copy.deepcopy(graph)
    dimensions = []
    for node_id, node in staged.items():
        if not isinstance(node, dict) or 'class_type' not in node:
            continue
        cls = node['class_type']
        inp = node.setdefault('inputs', {})
        schema = (info or {}).get(cls, {}).get('input', {})
        declared = {**schema.get('required', {}), **schema.get('optional', {})}
        for width, height in PAIRS:
            present = width in inp and height in inp
            supported = all(isinstance(declared.get(k), (list, tuple)) and declared[k][0] == 'INT'
                            for k in (width, height))
            if present or supported:
                score = (20 if cls in NATIVE else 0) + (5 if any(k in inp or k in declared for k in ('length', 'frames', 'num_frames', 'frame_count')) else 0)
                dimensions.append((score, str(node_id), node, width, height))
                break
    if not dimensions:
        inventory = '; '.join(str(k)+':'+str(n.get('class_type'))+'('+','.join(n.get('inputs', {}))+')'
                              for k, n in staged.items() if isinstance(n, dict) and 'class_type' in n)
        raise ValueError('Workflow MiniMax H3 : aucune entrée de dimensions reconnue dans le graphe ou les nœuds installés. '
                         'Exporte le workflow H3 au format API. Nœuds : '+inventory[:1400])
    native = [d for d in dimensions if d[2]['class_type'] in NATIVE]
    targets = native or [max(dimensions, key=lambda d: d[0])]
    for _, _, node, width, height in targets:
        # Replace the consumer inputs, never mutate a shared primitive upstream.
        node['inputs'][width] = int(p['width'])
        node['inputs'][height] = int(p['height'])
    for node in staged.values():
        if not isinstance(node, dict) or 'class_type' not in node:
            continue
        inp = node.setdefault('inputs', {})
        cls = node['class_type']
        for key in ('length', 'frames', 'frame_count', 'num_frames'):
            if key in inp:
                inp[key] = int(p['frames'])
        if cls in NATIVE:
            # H3 snaps to 17k+5 frames, unlike Wan's 4k+1 grid.
            inp['length'] = 5 + 17 * max(0, (int(p['frames']) - 5 + 16) // 17)
        for key in ('steps', 'seed', 'noise_seed'):
            if key in inp:
                inp[key] = int(p['steps'] if key == 'steps' else p['seed'])
        compact = cls.lower().replace('_', '')
        if any(x in compact for x in ('savevideo', 'saveimage', 'videocombine')):
            if 'filename_prefix' in inp:
                inp['filename_prefix'] = prefix
    graph.clear()
    graph.update(staged)
    return [(score, node_id, node) for score, node_id, node, _, _ in targets]
