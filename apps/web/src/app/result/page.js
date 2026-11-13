import { Suspense } from 'react';
import Result from '../../features/roadmap/Result';
export default function Page() { return <Suspense fallback={<p role="status">결과를 불러오는 중입니다…</p>}><Result/></Suspense>; }
