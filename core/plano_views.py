
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import Project, Lot, LotGeometry


@login_required
def plano_lotes(request):
    projects = Project.objects.order_by("name")
    project_id = request.GET.get("proyecto")

    project = (
        get_object_or_404(Project, pk=project_id)
        if project_id
        else projects.first()
    )

    if project is None:
        return render(request, "core/plano_lotes.html", {
            "projects": projects,
            "project": None,
            "lots": [],
            "markers_json": "[]",
            "plan_image_url": None,
        })

    lots = list(
        Lot.objects.filter(project=project)
        .select_related("block_ref")
        .order_by("number")
    )

    plan_image_url = (
        project.plan_image.url if project.plan_image else None
    )

    geometries = LotGeometry.objects.filter(
        lot__project=project
    ).select_related("lot")

    markers = []

    for geometry in geometries:
        lot = geometry.lot
        if not geometry.points:
            continue

        markers.append({
            "lot_id": lot.id,
            "lot_number": str(lot.number),
            "status": lot.status,
            "points": geometry.points,
        })

    selected_id = request.GET.get("lote")
    selected_lot = next(
        (lot for lot in lots if str(lot.id) == str(selected_id)),
        None,
    )

    return render(request, "core/plano_lotes.html", {
        "projects": projects,
        "project": project,
        "lots": lots,
        "markers_json": json.dumps(markers, ensure_ascii=False),
        "selected_lot": selected_lot,
        "plan_image_url": plan_image_url,
    })


@login_required
@require_POST
def guardar_geometria_lote(request):
    try:
        data = json.loads(request.body)
        lot_id = data.get("lot_id")
        points = data.get("points")

        if not isinstance(points, list) or len(points) < 3:
            return JsonResponse({
                "ok": False,
                "error": "El contorno debe tener al menos 3 puntos.",
            }, status=400)

        for point in points:
            if not isinstance(point, dict):
                return JsonResponse({
                    "ok": False,
                    "error": "Formato de punto no válido.",
                }, status=400)

            x = point.get("x")
            y = point.get("y")

            if (
                not isinstance(x, (int, float))
                or isinstance(x, bool)
                or not isinstance(y, (int, float))
                or isinstance(y, bool)
                or not 0 <= x <= 1
                or not 0 <= y <= 1
            ):
                return JsonResponse({
                    "ok": False,
                    "error": "Las coordenadas deben estar entre 0 y 1.",
                }, status=400)

        lot = get_object_or_404(Lot, pk=lot_id)

        geometry, _ = LotGeometry.objects.update_or_create(
            lot=lot,
            defaults={"points": points, "page_number": 1},
        )

        return JsonResponse({
            "ok": True,
            "lot_id": lot.id,
            "points": geometry.points,
        })

    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({
            "ok": False,
            "error": "No se pudieron interpretar los datos enviados.",
        }, status=400)
