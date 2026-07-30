from django.contrib import messages
from django.shortcuts import redirect, render

from .forms import RedacaoForm


def pagina_inicial(request):
    if request.method == "POST":
        form = RedacaoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Redação enviada com sucesso. Os dados foram salvos para análise futura.",
            )
            return redirect("redacoes:inicio")

        messages.error(
            request,
            "Não foi possível enviar a redação. Revise os campos destacados.",
        )
    else:
        form = RedacaoForm()

    return render(request, "redacoes/inicio.html", {"form": form})
