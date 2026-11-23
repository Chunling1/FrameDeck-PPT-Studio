"""Two live calls on synthetic material. Run only on explicit request."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import art_direction as art
import providers
from engine import validate_review

sample={"kind":"content","title":"同一段降温不能唯一定位原因","conclusion":"需要核对事件记录，才能区分看似相同的温度变化。",
        "copy":["比较两种可能解释：开窗换气、供热暂降。"],"visual":"两种解释，共用一个观测窗口；定性示意。",
        "layout":"left","asset":"","claims":[],"chart":None,"steps":[]}
s={"demo":False,"usage":[],"brief":"教学示意，不声称采集过实测数据。","audience":"答辩评委","assets":[],
   "plan":{"thesis":sample["conclusion"],"style":"白底技术剖面，蓝灰表示建筑和管路，橙色只标变化。","slides":[sample]}}
if __name__=="__main__":
    with TemporaryDirectory() as tmp:
        root=Path(tmp);(root/"cache").mkdir();art.generate(s,root)
    verdict=validate_review(providers.ask("auditor","输出 JSON：{pass:布尔, issues:[硬错误], advice:一句审美意见}。检查图是否把两种候选原因伪装成已确定因果，有无伪造实测；如有硬错误必须拒绝。",{"example":sample,"direction":s["directions"][0]},ledger=s["usage"]))
    out=Path(sys.argv[1]);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"page":sample,"direction":s["directions"][0],"review":verdict,"calls":s["usage"]},ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"models":[u["model"] for u in s["usage"]],"review":verdict,"output":str(out)},ensure_ascii=False))
