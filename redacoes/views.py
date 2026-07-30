from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .forms import RedacaoForm
from .models import Redacao
from .services.vision_service import VisionServiceError, extrair_texto_documento


@require_http_methods(["GET", "POST"])
def pagina_inicial(request):
    if request.method == "POST":
        form = RedacaoForm(request.POST, request.FILES)
        if form.is_valid():
            redacao = form.save()

            if redacao.imagem:
                redacao.status = Redacao.Status.PROCESSANDO
                redacao.save(update_fields=["status", "atualizada_em"])

                try:
                    redacao.texto_transcrito = extrair_texto_documento(
                        redacao.imagem
                    )
                except VisionServiceError as erro:
                    redacao.status = Redacao.Status.ERRO
                    messages.error(request, str(erro))
                else:
                    redacao.status = Redacao.Status.CONCLUIDA
                    if redacao.texto_transcrito:
                        messages.success(
                            request,
                            "OCR concluído. Confira o texto extraído abaixo.",
                        )
                    else:
                        messages.warning(
                            request,
                            "O OCR foi concluído, mas nenhum texto foi reconhecido na imagem.",
                        )

                redacao.save(
                    update_fields=[
                        "texto_transcrito",
                        "status",
                        "atualizada_em",
                    ]
                )
            else:
                messages.success(
                    request,
                    "Redação salva com sucesso. Nenhum OCR foi necessário.",
                )

            return redirect("redacoes:revisao", pk=redacao.pk)

        messages.error(
            request,
            "Não foi possível enviar a redação. Revise os campos destacados.",
        )
    else:
        form = RedacaoForm()

    return render(request, "redacoes/inicio.html", {"form": form})


@require_GET
def revisar_redacao(request, pk):
    redacao = get_object_or_404(Redacao, pk=pk)
    return render(request, "redacoes/revisao.html", {"redacao": redacao})
