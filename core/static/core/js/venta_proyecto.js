
document.addEventListener("DOMContentLoaded", function () {
    const proyecto = document.getElementById("id_project");
    const lote = document.getElementById("id_lot");

    if (!proyecto || !lote) return;

    async function cargarLotes() {
        const projectId = proyecto.value;

        lote.innerHTML = '<option value="">Seleccione un lote</option>';
        lote.disabled = true;

        if (!projectId) {
            lote.disabled = false;
            return;
        }

        try {
            const url = `/lotes-disponibles-por-proyecto/?project_id=${encodeURIComponent(projectId)}`;
            const response = await fetch(url);

            if (!response.ok) {
                throw new Error("Error al consultar los lotes");
            }

            const data = await response.json();

            data.lotes.forEach(function (item) {
                const opcion = document.createElement("option");
                opcion.value = item.id;
                opcion.textContent = `Lote ${item.numero}${item.manzana ? " — " + item.manzana : ""}`;
                lote.appendChild(opcion);
            });
        } catch (error) {
            console.error("Error al cargar los lotes:", error);
            alert("No se pudieron cargar los lotes del proyecto.");
        } finally {
            lote.disabled = false;
        }
    }

    proyecto.addEventListener("change", cargarLotes);
});
