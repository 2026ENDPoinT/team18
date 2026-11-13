import { Stepper, Heading, Footer } from '../../../components/layout/Shell';
import ProjectExperienceReview from '../../../features/roadmap/ProjectExperienceReview';
export default function Page() { return <><Stepper current={3}/><Heading number="05" title="역량 탐색" description="문서에서 확인한 수행 내용과 기술 경험을 검토하는 단계입니다."/><ProjectExperienceReview/><Footer previous="/input/courses" next="/result" nextLabel="다음: 로드맵 결과"/></>; }
