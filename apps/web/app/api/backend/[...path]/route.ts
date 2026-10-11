import {NextRequest,NextResponse} from 'next/server';
import {proxy} from '../../proxy';
export const dynamic='force-dynamic';
async function handle(req:NextRequest,{params}:{params:Promise<{path:string[]}>}){
  const {path}=await params; const joined=path.join('/');
  const allowed=req.method==='GET'?/^(me|runs|runs\/[a-f0-9-]{36})$/:/^(runs|runs\/[a-f0-9-]{36}\/actions\/[a-f0-9-]{36}\/execute)$/;
  if(!allowed.test(joined))return NextResponse.json({error:'Unknown route'},{status:404});
  return proxy(req,'/api/'+joined);
}
export {handle as GET,handle as POST};
