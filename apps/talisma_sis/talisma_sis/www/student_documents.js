frappe.ready(() => {
	document.querySelectorAll('.upload-student-document').forEach((button) => {
		button.addEventListener('click', async () => {
			const card = button.closest('.document-card');
			const file = card.querySelector('.document-file').files[0];
			const expiry = card.querySelector('.document-expiry')?.value || null;
			if (!file) return frappe.msgprint(__('Choose a document to upload.'));
			button.disabled = true;
			button.textContent = __('Uploading...');
			try {
				const form = new FormData();
				form.append('file', file);
				form.append('is_private', '1');
				form.append('folder', 'Home/Attachments');
				const response = await fetch('/api/method/upload_file', {method:'POST',headers:{'X-Frappe-CSRF-Token':frappe.csrf_token},body:form});
				const uploaded = await response.json();
				if (!response.ok || uploaded.exc) throw new Error(uploaded.message || __('Upload failed.'));
				await frappe.call({method:'talisma_sis.student_documents.upload_student_document',args:{document:card.dataset.document,file_url:uploaded.message.file_url,expiry_date:expiry}});
				window.location.reload();
			} catch (error) {
				frappe.msgprint(error.message || __('Unable to upload the document.'));
				button.disabled = false;
				button.textContent = __('Upload Document');
			}
		});
	});
});
