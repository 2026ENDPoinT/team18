export async function openCourseConfirmation(page) {
 const dialog = page.getByRole('dialog', { name: '이수 과목 확인', exact: true });
 if (!await dialog.isVisible()) await page.getByRole('button', { name: '이수 선택 확인', exact: true }).click();
 await dialog.waitFor();
 return dialog;
}

export async function confirmCourseSelection(page) {
 const dialog = await openCourseConfirmation(page);
 await dialog.getByRole('button', { name: '확인하고 역량 탐색', exact: true }).click();
}
