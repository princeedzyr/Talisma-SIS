frappe.ui.form.on('Student Report Generation Tool', {
  onload(frm) {
    if (frappe.boot?.sitename !== 'demo.talisma.local') return

    frm.set_query('assessment_group', () => ({
      filters: {
        is_group: 1,
        name: ['!=', 'All Assessment Groups'],
      },
    }))
  },
})
