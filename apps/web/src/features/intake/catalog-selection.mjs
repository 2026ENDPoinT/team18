// Only use selectable catalogs returned for the selected department.
export function chooseCatalog(catalogs, savedId, academicYear = new Date().getFullYear()) {
  const saved = catalogs.find(c => c.catalog_id === savedId);
  if (saved) return saved.catalog_id;
  const ranked = [...catalogs].sort((a, b) => {
    const aYear = Number(a.curriculum_year) || 0, bYear = Number(b.curriculum_year) || 0;
    return Number(bYear === academicYear) - Number(aYear === academicYear)
      || bYear - aYear || a.catalog_id.localeCompare(b.catalog_id);
  });
  return ranked[0]?.catalog_id || '';
}
