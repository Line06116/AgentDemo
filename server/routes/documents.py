import os
from fastapi import APIRouter, UploadFile, File, HTTPException

from rag.vector_store import VectorStoreService
from utils.file_handler import txt_loader, pdf_loader, md_loader, get_file_md5_hex
from utils.path_tool import get_abs_path

router = APIRouter()
vs = VectorStoreService()
DOCS_DIR = get_abs_path("data/documents")
MD5_FILE = os.path.join(DOCS_DIR, ".md5_records")


def _load_md5_records() -> dict:
    if not os.path.exists(MD5_FILE):
        return {}
    records = {}
    with open(MD5_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "," in line:
                md5, fname = line.split(",", 1)
                records[md5] = fname
    return records


def _save_md5_record(md5: str, fname: str):
    with open(MD5_FILE, "a", encoding="utf-8") as f:
        f.write(f"{md5},{fname}\n")


def _remove_md5_record(fname: str):
    records = _load_md5_records()
    records = {k: v for k, v in records.items() if v != fname}
    with open(MD5_FILE, "w", encoding="utf-8") as f:
        for md5, fn in records.items():
            f.write(f"{md5},{fn}\n")


LOADERS = {
    ".pdf": pdf_loader,
    ".txt": txt_loader,
    ".md": md_loader,
}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in LOADERS:
        raise HTTPException(400, f"不支持的文件类型: {ext}，支持: {list(LOADERS.keys())}")

    content = await file.read()
    save_path = os.path.join(DOCS_DIR, file.filename)
    with open(save_path, "wb") as f:
        f.write(content)

    md5 = get_file_md5_hex(save_path)
    records = _load_md5_records()
    if md5 in records:
        os.remove(save_path)
        return {"status": "skipped", "message": f"文件 {file.filename} 已存在（MD5 重复）"}

    try:
        loader = LOADERS[ext]
        docs = loader(save_path)
        vs.add_documents(docs)
        _save_md5_record(md5, file.filename)
        return {"status": "ok", "message": f"文件 {file.filename} 已入库", "chunks": len(docs)}
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(500, f"文件处理失败: {str(e)}")


@router.get("/documents")
async def list_documents():
    files = []
    if os.path.exists(DOCS_DIR):
        for f in os.listdir(DOCS_DIR):
            path = os.path.join(DOCS_DIR, f)
            if os.path.isfile(path) and not f.startswith("."):
                size = os.path.getsize(path)
                files.append({"name": f, "size": size, "size_display": f"{size / 1024:.1f} KB"})
    return {"files": files}


@router.delete("/documents/{filename}")
async def delete_document(filename: str):
    file_path = os.path.join(DOCS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, "文件不存在")

    os.remove(file_path)
    _remove_md5_record(filename)
    try:
        vs.collection.delete(where={"source": filename})
    except Exception:
        pass
    return {"status": "ok", "message": f"文件 {filename} 已删除"}
