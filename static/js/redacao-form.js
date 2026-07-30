document.addEventListener("DOMContentLoaded", () => {
    const imageInput = document.querySelector("#id_imagem");
    const previewContainer = document.querySelector("#image-preview");
    const previewImage = document.querySelector("#preview-image");
    const removeImageButton = document.querySelector("#remove-image");
    const textArea = document.querySelector("#id_texto_original");
    const characterCount = document.querySelector("#character-count");

    const updateCharacterCount = () => {
        if (!textArea || !characterCount) return;
        const total = textArea.value.length;
        characterCount.textContent = `${total} ${total === 1 ? "caractere" : "caracteres"}`;
    };

    const clearPreview = () => {
        if (!imageInput || !previewContainer || !previewImage) return;
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

        previewImage.src = URL.createObjectURL(file);
        previewContainer.classList.remove("d-none");
    });

    removeImageButton?.addEventListener("click", clearPreview);
    textArea?.addEventListener("input", updateCharacterCount);
    updateCharacterCount();
});
