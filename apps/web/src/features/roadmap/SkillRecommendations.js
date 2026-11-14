import { recommendedSkills } from './jobSkillAnalysis.mjs';

export default function SkillRecommendations({ comparison }) {
 const skills = recommendedSkills(comparison);
 return <section className="skill-recommendations" aria-label="보완할 역량 추천">
  <h3>보완할 역량 추천</h3>
  <p role="status">현재 보완할 역량 후보 {skills.length}개</p>
  {skills.length ? <ul className="result-brief-list">{skills.map(skill => <li key={skill.name} data-recommended-skill={skill.name}><b>{skill.name}</b></li>)}</ul>
   : <p>현재 보완할 역량 추천이 없습니다. 경험 체크를 해제하면 기존 기준에 따라 다시 표시됩니다.</p>}
  <p className="field-help">경험 미확인 기술은 경험 여부를 먼저 확인해 주세요. 직접 표시한 경험과 문서에서 확인한 경험은 별도로 관리합니다.</p>
 </section>;
}
