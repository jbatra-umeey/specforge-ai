import {NextRequest,NextResponse} from 'next/server';
export async function proxy(req:NextRequest,path:string){
  // Never inject a shared server credential: every caller must authenticate.
  const auth=req.headers.get('authorization'); const key=req.headers.get('x-api-key');
  const mode=process.env.AUTH_MODE||'development';
  if(process.env.SPECFORGE_ENV==='production'&&mode!=='oidc')return NextResponse.json({error:'Authentication misconfigured'},{status:503});
  if(mode==='oidc'?!auth?.startsWith('Bearer '):!key)return NextResponse.json({error:'Sign in required'},{status:401});
  const headers:Record<string,string>={'Content-Type':'application/json'};
  if(mode==='oidc'&&auth)headers.Authorization=auth;
  else if(key)headers['X-API-Key']=key;
  const id=req.headers.get('idempotency-key'); if(id)headers['Idempotency-Key']=id;
  const body=req.method==='GET'?undefined:await req.text();
  if(body&&body.length>32000)return NextResponse.json({error:'Request too large'},{status:413});
  try{
    const r=await fetch((process.env.INTERNAL_API_URL||'http://127.0.0.1:8000')+path,{method:req.method,headers,body,cache:'no-store',redirect:'error',signal:AbortSignal.timeout(240000)});
    return NextResponse.json(await r.json(),{status:r.status,headers:{'Cache-Control':'no-store'}});
  }catch{return NextResponse.json({error:'Backend unavailable or timed out. Refresh run history before retrying.'},{status:502})}
}
