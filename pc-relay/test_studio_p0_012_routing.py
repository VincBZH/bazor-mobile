import tempfile
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bazor_action_engine", HERE / "bazor_action_engine.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ActionEngine = mod.ActionEngine


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "studio"
        data = Path(td) / "data"
        (root / "app").mkdir(parents=True)

        # Bruit de réparation/modèles: même avec des mots de génération,
        # il ne doit jamais entrer dans le contexte P0-012.
        (root / "app" / "model_setup.py").write_text(
            "workflow='x'\nsource_media='legacy.png'\nrequested_mode='i2v'\n",
            encoding="utf-8",
        )

        # Générique ComfyUI/workflow sans vrai signal de routage: rejeté.
        (root / "app" / "workflow_helper.py").write_text(
            "def generate(prompt):\n    return comfyui_workflow(prompt)\n",
            encoding="utf-8",
        )

        # Vrai code de routage: accepté.
        (root / "app" / "generation_router.py").write_text(
            """
def route_generation(requested_mode, source_media=None):
    effective_mode = requested_mode
    if requested_mode == "t2i":
        source_media = None
        route = "sdxl_text_to_image"
    elif requested_mode in ("i2i", "i2v") and not source_media:
        raise ValueError("source_required")
    else:
        route = requested_mode
    return {
        "requested_mode": requested_mode,
        "effective_mode": effective_mode,
        "source_media": source_media,
        "route": route,
    }
""".strip(),
            encoding="utf-8",
        )

        eng = ActionEngine(data)
        eng.roots["simple_studio"] = root

        _, meta = eng.context_for_project(
            "simple-studio",
            max_files=10,
            max_chars=20000,
            focus="STUDIO-P0-012 T2I I2I T2V I2V source_media requested_mode effective_mode route",
        )

        paths = [x["path"].replace("\\", "/") for x in meta["files"]]
        assert meta["routing_focus"] is True, meta
        assert meta["routing_context_ok"] is True, meta
        assert meta["routing_strong_candidates"] >= 1, meta
        assert "app/generation_router.py" in paths, paths
        assert "app/model_setup.py" not in paths, paths
        assert "app/workflow_helper.py" not in paths, paths

        print("STUDIO_P0_012_ROUTING_CONTEXT_OK", meta["routing_strong_candidates"], paths)


if __name__ == "__main__":
    main()
