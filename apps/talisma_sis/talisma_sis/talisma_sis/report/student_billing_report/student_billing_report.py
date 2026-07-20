from talisma_sis.finance_reports import billing_report


def execute(filters=None):
	return billing_report(filters)
