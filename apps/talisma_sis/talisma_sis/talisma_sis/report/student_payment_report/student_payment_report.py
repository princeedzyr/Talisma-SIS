from talisma_sis.finance_reports import payment_report


def execute(filters=None):
	return payment_report(filters)
