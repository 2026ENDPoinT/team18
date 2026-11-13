// Corrections are user statements; keep the original evidence untouched.
export function experiencePresentation(item) {
 const correction = item.user_answer?.status === 'corrected' ? item.user_answer.correction : null;
 return correction || item;
}
