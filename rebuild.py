import json
from pathlib import Path
from render import decks,proof

if __name__=="__main__":
    root=Path(__file__).resolve().parent
    scenes=json.loads((root/"scenes.json").read_text(encoding="utf8"))
    (root/"output").mkdir(exist_ok=True);(root/"pages").mkdir(exist_ok=True)
    locked=root/"locked-scenes.json"
    fallback=json.loads(locked.read_text(encoding="utf8")) if locked.exists() else scenes
    for i,scene in enumerate(fallback,1):
        image=root/f"pages/{i:02}.png"
        if not image.is_file():
            proof(scene,root,image)
    decks(scenes,root,root/"output")
    print(root/"output")
