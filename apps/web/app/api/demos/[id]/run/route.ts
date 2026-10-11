import {NextRequest,NextResponse} from 'next/server';
import {proxy} from '../../../proxy';
export async function POST(req:NextRequest,{params}:{params:Promise<{id:string}>}){
  const {id}=await params;
  if(!['feature','regression','drift','incident','release'].includes(id))return NextResponse.json({error:'Unknown demo'},{status:404});
  return proxy(req,'/api/demos/'+id+'/run');
}
