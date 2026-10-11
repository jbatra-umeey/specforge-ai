"""Allowlisted local tools: never eval arbitrary code or spawn untrusted commands."""
from pathlib import Path
from .security import require_approval
class ToolRegistry:
    def __init__(self,root:Path):self.root=root.resolve()
    def _path(self,relative:str)->Path:
        target=(self.root/relative).resolve()
        if not target.is_relative_to(self.root):raise ValueError('Path escapes workspace')
        return target
    def read_file(self,path:str)->str:
        f=self._path(path)
        if not f.is_file() or f.stat().st_size>100_000:raise ValueError('File missing or too large')
        return f.read_text()
    def write_file(self,path:str,content:str,approved:bool=False):
        require_approval(approved)
        target=self._path(path)
        if len(content)>100_000:raise ValueError('Write too large')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(content)
        return {'path':path,'bytes':len(content.encode())}
