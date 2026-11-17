// Unfold's file inputs show only the first file's name. For "Add photos",
// show how many were picked. Runs after Unfold's own listener on the input.
document.addEventListener("change", (event) => {
  const input = event.target;
  if (input.type !== "file" || !input.multiple || input.files.length < 2) {
    return;
  }
  const label = input.closest("label").querySelector("input[type=text]");
  label.setAttribute("value", `${input.files.length} photos selected`);
});
