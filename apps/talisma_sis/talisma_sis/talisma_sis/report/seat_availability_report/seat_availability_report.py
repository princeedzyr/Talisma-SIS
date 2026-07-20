from talisma_sis.admission_reports import seat_availability_report


def execute(filters=None):
	return seat_availability_report(filters)
