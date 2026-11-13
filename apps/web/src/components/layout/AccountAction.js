'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { authClient } from '../../lib/api/auth';
import { clearSelectedPlan, signOutSession } from '../../lib/api/session';

export default function AccountAction() {
 const router = useRouter();
 const [user, setUser] = useState(null), [ready, setReady] = useState(false);
 const [busy, setBusy] = useState(false), [error, setError] = useState('');
 const lock = useRef(false);
 useEffect(() => {
  let subscription;
  try {
   // INITIAL_SESSION also restores the label on a direct visit or reload.
   subscription = authClient().auth.onAuthStateChange((event, session) => {
    setUser(session?.user || null); setReady(true);
    if (event === 'SIGNED_OUT') { clearSelectedPlan(); setError(''); }
   }).data.subscription;
  } catch { setReady(true); }
  return () => subscription?.unsubscribe();
 }, []);
 async function logout() {
  if (lock.current) return;
  if (user?.is_anonymous && !window.confirm('게스트 세션을 종료하면 이 데이터를 자동으로 복원할 수 없습니다. 로그아웃할까요?')) return;
  lock.current = true; setBusy(true); setError('');
  try {
   await signOutSession();
   router.replace('/');
  } catch { setError('로그아웃하지 못했습니다. 다시 시도해 주세요.'); }
  finally { lock.current = false; setBusy(false); }
 }
 return <div className="account-action">
  {!ready ? <button type="button" className="account-link" disabled>계정 확인 중…</button>
   : user ? <button type="button" className="account-link" onClick={logout} disabled={busy}>{busy ? '로그아웃 중…' : '로그아웃'}</button>
   : <Link href="/" className="account-link">계정 · 로그인</Link>}
  {error && <p className="account-error" role="alert">{error}</p>}
 </div>;
}
