(function () {
  const uploadForm = document.getElementById('upload-form');
  const uploadStatus = document.getElementById('upload-status');
  const fetchDriveButton = document.getElementById('fetch-drive');
  const ingestButton = document.getElementById('ingest-selected');
  const driveStatus = document.getElementById('drive-status');
  const driveTableBody = document.querySelector('#drive-files tbody');
  const driveVectorStoreInput = document.getElementById('drive-vector-store');
  const driveFolderInput = document.getElementById('drive-folder');
  const csrfToken = document.body.dataset.csrfToken;

  let currentFolderId = null;

  function humanBytes(value) {
    const units = ['bytes', 'KB', 'MB', 'GB'];
    let size = Number(value);
    for (const unit of units) {
      if (size < 1024 || unit === units[units.length - 1]) {
        return unit === 'bytes' ? `${Math.round(size)} ${unit}` : `${size.toFixed(1)} ${unit}`;
      }
      size /= 1024;
    }
    return `${value} bytes`;
  }

  function setStatus(element, message, isError = false) {
    if (!element) return;
    element.textContent = message || '';
    element.classList.toggle('muted', !isError && message);
    element.classList.toggle('alert-error', Boolean(isError && message));
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!uploadForm) return;
    const formData = new FormData(uploadForm);
    if (!formData.get('file')) {
      setStatus(uploadStatus, 'Please select a file to upload.', true);
      return;
    }
    if (!formData.get('vector_store_name')) {
      setStatus(uploadStatus, 'Provide a vector store name.', true);
      return;
    }

    setStatus(uploadStatus, 'Uploading…');
    try {
      const response = await fetch('/admin/vector-store/upload', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Upload failed');
      }
      const payload = await response.json();
      setStatus(
        uploadStatus,
        `Uploaded ${payload.filename} · ${humanBytes(payload.size_bytes)} (vector store ${payload.vector_store_id})`
      );
      uploadForm.reset();
      setTimeout(() => window.location.reload(), 1200);
    } catch (error) {
      console.error(error);
      setStatus(uploadStatus, error.message || 'Upload failed', true);
    }
  }

  async function fetchDriveFiles() {
    const folderLink = driveFolderInput?.value?.trim();
    if (!folderLink) {
      setStatus(driveStatus, 'Provide a shared folder link first.', true);
      return;
    }
    setStatus(driveStatus, 'Fetching files…');
    ingestButton.disabled = true;
    driveTableBody.innerHTML = '';

    try {
      const response = await fetch(
        `/admin/google-drive/files?folder_link=${encodeURIComponent(folderLink)}`
      );
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Unable to list folder');
      }
      const data = await response.json();
      currentFolderId = data.folderId;
      if (!Array.isArray(data.files) || data.files.length === 0) {
        setStatus(driveStatus, 'No ingestible files found in this folder.', true);
        return;
      }
      const fragment = document.createDocumentFragment();
      data.files.forEach((file) => {
        const row = document.createElement('tr');
        const checkboxCell = document.createElement('td');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = file.id;
        checkbox.addEventListener('change', updateIngestState);
        checkboxCell.appendChild(checkbox);
        row.appendChild(checkboxCell);

        const nameCell = document.createElement('td');
        nameCell.textContent = file.name;
        row.appendChild(nameCell);

        const typeCell = document.createElement('td');
        typeCell.textContent = file.mimeType;
        row.appendChild(typeCell);

        const sizeCell = document.createElement('td');
        sizeCell.textContent = humanBytes(file.size);
        row.appendChild(sizeCell);

        const modifiedCell = document.createElement('td');
        modifiedCell.textContent = file.modifiedTime || '–';
        row.appendChild(modifiedCell);

        fragment.appendChild(row);
      });
      driveTableBody.appendChild(fragment);
      setStatus(driveStatus, `${data.files.length} file(s) ready.`);
      updateIngestState();
    } catch (error) {
      console.error(error);
      setStatus(driveStatus, error.message || 'Unable to list folder', true);
    }
  }

  function updateIngestState() {
    if (!ingestButton) {
      return;
    }
    const selected = driveTableBody.querySelectorAll('input[type="checkbox"]:checked');
    ingestButton.disabled = selected.length === 0;
  }

  async function ingestSelected() {
    const vectorStoreName = driveVectorStoreInput?.value?.trim();
    if (!vectorStoreName) {
      setStatus(driveStatus, 'Vector store name is required.', true);
      return;
    }
    const selected = Array.from(
      driveTableBody.querySelectorAll('input[type="checkbox"]:checked')
    ).map((input) => input.value);
    if (selected.length === 0) {
      setStatus(driveStatus, 'Select at least one file to ingest.', true);
      return;
    }
    if (!currentFolderId) {
      setStatus(driveStatus, 'Fetch the folder contents first.', true);
      return;
    }

    ingestButton.disabled = true;
    setStatus(driveStatus, 'Ingesting selected files…');
    try {
      const response = await fetch('/admin/google-drive/ingest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken || '',
        },
        body: JSON.stringify({
          vector_store_name: vectorStoreName,
          folder_id: currentFolderId,
          file_ids: selected,
        }),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'Ingestion failed');
      }
      const payload = await response.json();
      setStatus(
        driveStatus,
        `Ingested ${payload.length} file(s). Refreshing…`
      );
      setTimeout(() => window.location.reload(), 1500);
    } catch (error) {
      console.error(error);
      setStatus(driveStatus, error.message || 'Ingestion failed', true);
      updateIngestState();
    }
  }

  uploadForm?.addEventListener('submit', handleUpload);
  fetchDriveButton?.addEventListener('click', fetchDriveFiles);
  ingestButton?.addEventListener('click', ingestSelected);
})();
