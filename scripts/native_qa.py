"""Independent Office rendering comparison. No slide data leaves the machine."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from PIL import Image,ImageStat,ImageChops


def check(project,output,office=None):
    office=office or shutil.which("soffice") or r"C:\Program Files\LibreOffice\program\soffice.exe"
    if not Path(office).is_file():raise RuntimeError("请安装 LibreOffice 或指定 --office")
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        scratch=Path(temp); subprocess.run([office,"-env:UserInstallation="+(scratch/"profile").as_uri(),"--headless","--convert-to","pdf","--outdir",str(scratch),str(project/"output/editable.pptx")],check=True,timeout=180)
        pdf=scratch/"editable.pdf"
        try:
            import pypdfium2 as pdfium
            doc=pdfium.PdfDocument(pdf);pages=[p.render(scale=1.4).to_pil().convert("RGB") for p in doc];doc.close()
        except ImportError:
            import fitz
            with fitz.open(pdf) as doc:pages=[Image.frombytes("RGB",(pix.width,pix.height),pix.samples) for p in doc for pix in [p.get_pixmap(matrix=fitz.Matrix(1.4,1.4))]]
    refs=sorted((project/"pages").glob("*.png"))
    if len(refs)!=len(pages):raise ValueError("渲染页数不符")
    scores=[]
    for i,(im,file) in enumerate(zip(pages,refs),1):
        ref=Image.open(file).convert("RGB");im=im.resize(ref.size)
        if max(ImageStat.Stat(im).stddev)<3:raise ValueError(f"第{i}页为空白")
        scores.append(round(sum(ImageStat.Stat(ImageChops.difference(im,ref)).mean)/3/255,4))
        comp=Image.new("RGB",(1280,360))
        comp.paste(ref.resize((640,360)),(0,0));comp.paste(im.resize((640,360)),(640,0));comp.save(output/f"{i:02}.png")
    (output/"qa.json").write_text(json.dumps({"renderer":"LibreOffice","pages":len(refs),"normalized_mean_pixel_difference":scores,"note":"数值用于定位差异，不等于审美结论；左锁版图，右独立渲染。"},ensure_ascii=False,indent=2),encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("project",type=Path);p.add_argument("output",type=Path);p.add_argument("--office");a=p.parse_args();check(a.project.resolve(),a.output.resolve(),a.office)
