from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from contas.decorators import aluno_required, professor_required

from .forms import CorrigirRedacaoForm, RedacaoForm, RevisaoTranscricaoForm
from .models import Redacao
from .services.ai_service import AIServiceError, avaliar_redacao
from .services.ocr_service import OCRServiceError, extrair_texto_documento


@require_http_methods(["GET"])
def landing_page(request):
    return render(request, "redacoes/landing.html")


@aluno_required
@require_http_methods(["GET"])
def home(request):
    redacoes = list(Redacao.objects.filter(aluno=request.user)[:20])
    concluidas = sum(1 for redacao in redacoes if redacao.resultado_json)
    return render(
        request,
        "redacoes/home.html",
        {"redacoes": redacoes, "total_concluidas": concluidas},
    )


@aluno_required
@require_http_methods(["GET", "POST"])
def pagina_inicial(request):
    if request.method == "GET":
        form = RedacaoForm()
        return render(request, "redacoes/inicio.html", {"form": form})

    form = RedacaoForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(
            request,
            "Não foi possível enviar a redação. Revise os campos destacados.",
        )
        return render(request, "redacoes/inicio.html", {"form": form})

    redacao = form.save(commit=False)
    redacao.aluno = request.user
    redacao.save()
    if redacao.imagem:
        _processar_ocr(request, redacao)
    else:
        messages.success(
            request,
            "Redação salva com sucesso. Nenhum OCR foi necessário.",
        )

    return redirect("redacoes:revisao", pk=redacao.pk)


@login_required
@require_http_methods(["GET", "POST"])
def revisar_redacao(request, pk):
    redacao = get_object_or_404(Redacao, pk=pk, aluno=request.user)

    if request.method == "GET":
        form = RevisaoTranscricaoForm(
            instance=redacao,
            initial={
                "texto_revisado": redacao.texto_revisado
                or redacao.texto_transcrito
                or redacao.texto_original
            },
        )
    else:
        form = RevisaoTranscricaoForm(request.POST, instance=redacao)
        if form.is_valid():
            redacao = form.save(commit=False)
            if _salvar_e_avaliar(request, redacao):
                return redirect("redacoes:resultado", pk=redacao.pk)
            return redirect("redacoes:revisao", pk=redacao.pk)
        messages.error(
            request,
            "Não foi possível confirmar o texto. Revise o campo destacado.",
        )

    return render(
        request,
        "redacoes/revisao.html",
        {"redacao": redacao, "form": form},
    )


@login_required
@require_http_methods(["GET"])
def resultado_redacao(request, pk):
    redacao = get_object_or_404(Redacao, pk=pk, aluno=request.user)
    if not redacao.resultado_json:
        messages.warning(
            request,
            "Esta redação ainda não possui uma avaliação concluída.",
        )
        return redirect("redacoes:revisao", pk=redacao.pk)

    return render(
        request,
        "redacoes/resultado.html",
        {"redacao": redacao, "resultado": redacao.resultado_json},
    )


@professor_required
@require_http_methods(["GET", "POST"])
def professor_corrigir_redacao(request, pk):
    redacao = get_object_or_404(
        Redacao, pk=pk, aluno__turma__professor=request.user
    )
    avaliacao_possivel = bool(redacao.resultado_json.get("avaliacao_possivel"))

    if request.method == "POST":
        form = CorrigirRedacaoForm(request.POST)
        if avaliacao_possivel:
            form_valido = form.is_valid()
        else:
            for nome_campo in list(form.fields):
                if nome_campo != "comentario_professor":
                    form.fields[nome_campo].required = False
            form_valido = form.is_valid()

        if form_valido:
            if avaliacao_possivel:
                redacao.resultado_json = form.aplicar_ao_resultado(redacao.resultado_json)
            redacao.comentario_professor = form.cleaned_data["comentario_professor"].strip()
            redacao.corrigido_por = request.user
            redacao.corrigido_em = timezone.now()
            redacao.save(
                update_fields=[
                    "resultado_json",
                    "comentario_professor",
                    "corrigido_por",
                    "corrigido_em",
                    "atualizada_em",
                ]
            )
            messages.success(request, "Correção atualizada com sucesso.")
            return redirect("redacoes:professor_corrigir_redacao", pk=redacao.pk)
    else:
        form = CorrigirRedacaoForm()
        form.initial_a_partir_de(redacao)

    return render(
        request,
        "redacoes/professor_corrigir_redacao.html",
        {
            "redacao": redacao,
            "form": form,
            "avaliacao_possivel": avaliacao_possivel,
        },
    )


def _processar_ocr(request, redacao: Redacao) -> None:
    redacao.status = Redacao.Status.PROCESSANDO
    redacao.save(update_fields=["status", "atualizada_em"])

    try:
        redacao.texto_transcrito = extrair_texto_documento(redacao.imagem)
    except OCRServiceError as erro:
        redacao.status = Redacao.Status.ERRO
        messages.error(request, str(erro))
    else:
        redacao.status = Redacao.Status.CONCLUIDA
        if redacao.texto_transcrito:
            messages.success(request, "OCR concluído. Confira o texto extraído abaixo.")
        else:
            messages.warning(
                request,
                "O OCR foi concluído, mas nenhum texto foi reconhecido na imagem.",
            )

    redacao.save(update_fields=["texto_transcrito", "status", "atualizada_em"])


def _salvar_e_avaliar(request, redacao: Redacao) -> bool:
    redacao.resultado_json = {}
    redacao.save(
        update_fields=["texto_revisado", "resultado_json", "atualizada_em"]
    )

    try:
        resultado = avaliar_redacao(redacao.tema, redacao.texto_revisado)
    except AIServiceError as erro:
        messages.error(
            request,
            f"Texto revisado salvo, mas a avaliação não foi concluída: {erro}",
        )
        return False

    redacao.resultado_json = resultado
    redacao.save(update_fields=["resultado_json", "atualizada_em"])
    messages.success(
        request,
        "Texto revisado salvo e avaliação estruturada concluída.",
    )
    return True
