from talisma_sis.finance_reports import account_statement


def execute(filters=None):
	return account_statement(filters)
