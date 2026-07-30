document.addEventListener("DOMContentLoaded", () => {
    const imageInput = document.querySelector("#id_imagem");
    const previewContainer = document.querySelector("#image-preview");
    const previewImage = document.querySelector("#preview-image");
    const removeImageButton = document.querySelector("#remove-image");
    const textArea = document.querySelector("#id_texto_original");
    const characterCount = document.querySelector("#character-count");
    let previewUrl = null;

    const revokePreviewUrl = () => {
        if (!previewUrl) return;
        URL.revokeObjectURL(previewUrl);
        previewUrl = null;
    };

    const updateCharacterCount = () => {
        if (!textArea || !characterCount) return;
        const total = textArea.value.length;
        characterCount.textContent = `${total} ${total === 1 ? "caractere" : "caracteres"}`;
    };

    const clearPreview = () => {
        if (!imageInput || !previewContainer || !previewImage) return;
        revokePreviewUrl();
        imageInput.value = "";
        previewImage.removeAttribute("src");
        previewContainer.classList.add("d-none");
    };

    imageInput?.addEventListener("change", () => {
        const file = imageInput.files?.[0];
        if (!file || !file.type.startsWith("image/")) {
            clearPreview();
            return;
        }

        revokePreviewUrl();
        previewUrl = URL.createObjectURL(file);
        previewImage.src = previewUrl;
        previewContainer.classList.remove("d-none");
    });

    removeImageButton?.addEventListener("click", clearPreview);
    textArea?.addEventListener("input", updateCharacterCount);
    window.addEventListener("pagehide", revokePreviewUrl);
    updateCharacterCount();
});
