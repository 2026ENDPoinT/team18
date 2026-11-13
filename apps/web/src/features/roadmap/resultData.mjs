// Read saved data only. Each resource settles independently so a failed roadmap
// never hides the student's profile or blocks goal-only activity recommendations.
export async function loadResultResources(apiRequest, id, receive) {
 const base = `/roadmap-inputs/${encodeURIComponent(id)}`;
 const read = async (key, path) => {
  receive(key, { phase: 'loading' });
  try {
   const data = path ? await apiRequest(path) : null;
   receive(key, { phase: 'ready', data });
   return data;
  } catch (error) {
   receive(key, { phase: 'error', message: error.message });
   return null;
  }
 };
 await Promise.all([
  read('plan', base).then(plan => plan
   ? read('courses', plan.input.catalog_id ? `${base}/courses?catalog_id=${encodeURIComponent(plan.input.catalog_id)}&page_size=1` : null)
   : receive('courses', { phase: 'error', message: '이수 정보를 확인하지 못했어요.' })),
  read('roadmap', `${base}/roadmap`),
  read('comparison', `${base}/skill-comparison`),
  read('activities', `${base}/activities`),
 ]);
}
