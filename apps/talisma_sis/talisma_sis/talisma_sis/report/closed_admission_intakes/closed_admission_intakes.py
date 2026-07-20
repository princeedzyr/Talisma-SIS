from talisma_sis.admission_reports import closed_admission_intakes


def execute(filters=None):
	return closed_admission_intakes(filters)
