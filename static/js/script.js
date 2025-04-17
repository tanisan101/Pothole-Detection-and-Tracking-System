function scrollToSection(sectionId) {
  document.querySelector(sectionId).scrollIntoView({ behavior: "smooth" });
}

function uploadFile() {
  const fileInput = document.getElementById('file-upload');
  const status = document.getElementById('upload-status');
  if (fileInput.files.length > 0) {
    status.textContent = 'File uploaded successfully!';
    status.style.color = 'green';
  } else {
    status.textContent = 'Please select a file.';
    status.style.color = 'red';
  }
}

function downloadReport() {
  alert("Report downloaded successfully!");
}

document.addEventListener("DOMContentLoaded", function () {
  const map = document.getElementById('map');
  map.innerHTML = '<p style="text-align:center; padding: 20px;">Map visualization coming soon!</p>';
});