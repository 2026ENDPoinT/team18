export function activityReason(item) {
 const saved = item.personalization_reason?.trim();
 if (saved) return saved;
 // Legacy snapshots have no generated paragraph. Show each verified witness once.
 const seen = new Set(), evidence = [];
 for (const entry of item.evidence || []) {
  const field = entry.posting_field, quote = entry.posting_quote;
  if (!['title', 'category', 'description_text'].includes(field) || !quote || item[field] !== quote ||
      !entry.matched_term || !quote.includes(entry.matched_term) || seen.has(quote)) continue;
  seen.add(quote);
  evidence.push(`공고 ${{ title: '제목', category: '분야', description_text: '본문' }[field]}에 “${quote.slice(0, 120)}${quote.length > 120 ? '…' : ''}”라고 안내되어 있습니다.`);
 }
 return evidence.length
  ? `${evidence[0]} 진로·경험과의 구체적인 연결과 실제 과제는 원문에서 확인해 주세요.`
  : '공고의 상세 활동 근거가 부족해 진로·경험과의 연결을 설명하기 어렵습니다. 원문에서 실제 과제와 결과물을 확인해 주세요.';
}
