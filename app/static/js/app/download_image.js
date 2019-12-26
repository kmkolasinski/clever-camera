function downloadImage(imageBytes, filename) {
    let data = `data:image/jpeg;base64,${imageBytes}`;
    let link = document.createElement('a');
    link.setAttribute('href', encodeURI(data));
    link.setAttribute('download', filename);
    link.setAttribute('target', "_blank");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
