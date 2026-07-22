"""Academic Term naming behavior for the Bryan University SIS."""

from education.education.doctype.academic_term.academic_term import (
	AcademicTerm as EducationAcademicTerm,
)


class AcademicTerm(EducationAcademicTerm):
	"""Use the explicit Term Name as both the record name and visible title."""

	def autoname(self) -> None:
		self.name = (self.term_name or "").strip()

	def set_title(self) -> None:
		self.title = (self.term_name or "").strip()
