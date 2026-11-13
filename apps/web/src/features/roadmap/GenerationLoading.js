import { generationTasks } from './generationFlow.mjs';

const labels = { pending: '대기 중', running: '진행 중', success: '완료', partial: '일부 제공', unavailable: '자료 없음', failed: '조회 실패' };
export default function GenerationLoading({ state, onRetry }) {
 const waitingForOtherWork = Object.values(state.tasks || {}).includes('failed') && state.phase === 'tracking';
 const error = ['failed', 'invalid', 'unknown'].includes(state.phase);
 return <section className="generation-screen" aria-labelledby="generation-title">
  <div className="generation-card">
   <div className="generation-mark" aria-hidden="true">✦</div>
   <h1 id="generation-title">맞춤형 진로 로드맵을 만들고 있어요</h1>
   <p className="generation-description">저장된 정보와 분석 자료로 수강 후보와 활동 추천을 확인하고 결과를 저장합니다.</p>
   <ul className="generation-tasks" aria-label="로드맵 생성 작업 상태" aria-live="polite" aria-atomic="true">
    {generationTasks.map(([key, name]) => {
     const status = state.tasks?.[key] || 'pending';
     return <li key={key}><span>{name}</span><span className={`generation-status ${status}`}><i aria-hidden="true">{status === 'success' ? '✓' : status === 'failed' ? '!' : status === 'pending' ? '●' : ''}</i>{labels[status]}</span></li>;
    })}
   </ul>
   {waitingForOtherWork && <p role="status">일부 자료를 조회하지 못했습니다. 나머지 결과를 확인하고 저장합니다.</p>}
   {error && <div className="generation-error" role="alert">
    <p>{state.phase === 'unknown' ? '로드맵 생성 상태를 확인하지 못했어요.' : '로드맵 생성 중 일부 작업을 완료하지 못했어요.'}</p>
    {state.phase === 'unknown' ? <p>서버 상태를 확인하지 못했습니다. 다시 시도하면 진행 중인 실행부터 확인합니다.</p> : state.detail && <p>{state.detail}</p>}
    <button type="button" className="primary" disabled={waitingForOtherWork} onClick={onRetry}>다시 시도</button>
   </div>}
  </div>
 </section>;
}
