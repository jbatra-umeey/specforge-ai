import {NextResponse} from 'next/server';
export const dynamic='force-dynamic';
export async function GET(){
  const mode=process.env.AUTH_MODE||'development';
  if(process.env.SPECFORGE_ENV==='production' && (mode!=='oidc'||!process.env.PUBLIC_APP_URL?.startsWith('https://')))
    return NextResponse.json({error:'Production authentication configuration is invalid'},{status:503});
  return NextResponse.json({mode,authority:process.env.OIDC_ISSUER||'',clientId:process.env.OIDC_CLIENT_ID||'',scope:process.env.OIDC_SCOPE||'openid profile',appUrl:process.env.PUBLIC_APP_URL||'http://localhost:3000'},{headers:{'Cache-Control':'no-store'}});
}
