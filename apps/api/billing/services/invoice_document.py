"""One source of truth for the invoice document.

The same context feeds the downloaded PDF, the on-screen preview and the PDF
attached to the e-mail. These three used to build their own contexts, which is
how the emailed copy silently stopped honouring an invoice's own pdf_overrides.
"""

from django.template.loader import render_to_string

UNIFIED_TEMPLATE = "billing/invoice_unified.html"


def _get_company_context(pdf_overrides=None):
    """Load company info from DB for invoice PDF context.

    If *pdf_overrides* is provided (a dict), its values take precedence over
    the company-level defaults for: pdf_show_rccm, pdf_show_nif,
    pdf_bank_display, pdf_selected_bank_indices, pdf_signatory_id.
    """
    from settings_app.models import CompanyInfo, Signatory

    info = CompanyInfo.load()
    ov = pdf_overrides or {}
    city_parts = [p for p in [info.city, info.country] if p]

    logo_path = None
    if info.logo:
        try:
            logo_path = info.logo.path
        except NotImplementedError:
            logo_path = None  # Remote storage (S3)

    # Filter bank accounts — use override if present
    all_banks = info.bank_accounts or []
    bank_display = ov.get("pdf_bank_display", info.pdf_bank_display)
    bank_indices = ov.get("pdf_selected_bank_indices", info.pdf_selected_bank_indices or [])
    if bank_display == "none":
        pdf_banks = []
    elif bank_display == "selected":
        pdf_banks = [b for i, b in enumerate(all_banks) if i in bank_indices]
    else:  # "all"
        pdf_banks = all_banks

    # Signatory — use override if key present, else company default
    signatory_title = ""
    signatory_name = ""
    signatory_image_src = None
    sig_id = ov.get("pdf_signatory_id", info.pdf_signatory_id)
    if sig_id:
        try:
            sig = Signatory.objects.get(pk=sig_id)
            signatory_title = sig.label
            signatory_name = sig.name  # may be empty string
            if sig.signature_image:
                try:
                    signatory_image_src = f"file://{sig.signature_image.path}"
                except Exception:
                    pass
        except Signatory.DoesNotExist:
            pass

    # RCCM / NIF — use override if key present
    show_rccm = ov.get("pdf_show_rccm", info.pdf_show_rccm)
    show_nif = ov.get("pdf_show_nif", info.pdf_show_nif)

    return {
        "company_name": info.company_name or info.display_name,
        "company_address": info.address,
        "company_city": ", ".join(city_parts),
        "company_phone": " / ".join(info.phone_numbers) if info.phone_numbers else "",
        "company_email": info.email,
        "company_logo_path": logo_path,
        "company_bank_accounts": pdf_banks,
        "company_rccm": info.rccm if show_rccm else "",
        "company_nif": info.nif if show_nif else "",
        "company_signatory_title": signatory_title,
        "company_signatory_name": signatory_name,
        "company_signatory_image": signatory_image_src,
    }

def _format_quantity(value):
    """Whole quantities print as integers; fractional ones keep their decimals."""
    if value == value.to_integral_value():
        return int(value)
    return value.normalize()


def build_invoice_document_context(invoice, request=None, for_pdf: bool = True) -> dict:
    """Template context for one invoice, exactly as it was generated.

    `for_pdf` only changes how images are addressed: WeasyPrint reads them from
    disk, a browser needs a URL. Everything else — including the invoice's own
    pdf_overrides — is identical in both cases.
    """
    from settings_app.services import (
        amount_in_words_fr, format_amount, format_currency, format_date_long,
    )

    company_ctx = _get_company_context(pdf_overrides=invoice.pdf_overrides)

    lines = []
    for line in invoice.lines.all():
        if line.line_type == "rent" and invoice.period_start and invoice.period_end:
            description = (
                f"Loyer du {format_date_long(invoice.period_start)} "
                f"au {format_date_long(invoice.period_end)}"
            )
        else:
            description = line.description
        lines.append({
            "line_type": line.line_type,
            # int() truncated cents on EUR/USD and would drop a fractional
            # quantity; format_amount already omits decimals when whole.
            "quantity": _format_quantity(line.quantity),
            "description": description,
            "unit_price": format_amount(line.unit_price),
            "amount": format_amount(line.amount),
        })

    logo_src = None
    signature_src = company_ctx.get("company_signatory_image")
    if for_pdf:
        if company_ctx.get("company_logo_path"):
            logo_src = f"file://{company_ctx['company_logo_path']}"
    else:
        from settings_app.models import CompanyInfo, Signatory

        info = CompanyInfo.load()
        if info.logo and request is not None:
            logo_src = request.build_absolute_uri(info.logo.url)
        if signature_src and signature_src.startswith("file://"):
            sig_id = (invoice.pdf_overrides or {}).get(
                "pdf_signatory_id", info.pdf_signatory_id
            )
            signature_src = None
            if sig_id and request is not None:
                sig = Signatory.objects.filter(pk=sig_id).first()
                if sig and sig.signature_image:
                    signature_src = request.build_absolute_uri(sig.signature_image.url)

    return {
        **company_ctx,
        "is_pdf": True,
        "logo_src": logo_src,
        "company_signatory_image": signature_src,
        "invoice_number": invoice.invoice_number,
        "issue_date": format_date_long(invoice.invoice_date or invoice.created_at.date()),
        "due_date": format_date_long(invoice.due_date) if invoice.due_date else "\u2014",
        "period_start": format_date_long(invoice.period_start) if invoice.period_start else "\u2014",
        "period_end": format_date_long(invoice.period_end) if invoice.period_end else "\u2014",
        "tenant_name": invoice.lease.tenant.display_name,
        "unit_name": invoice.lease.unit.name,
        "property_name": invoice.lease.unit.building.name,
        # Trailing whitespace in the stored address printed as "Street , City".
        "property_address": (invoice.lease.unit.building.address_line1 or "").strip(),
        "property_city": (invoice.lease.unit.building.city or "").strip(),
        "currency": format_currency(invoice.currency),
        "total_amount": format_amount(invoice.total_amount),
        "total_in_words": amount_in_words_fr(invoice.total_amount),
        "lines": lines,
        "notes": invoice.notes or "",
    }


def render_invoice_document(invoice, request=None, for_pdf: bool = True) -> str:
    """The invoice document as HTML."""
    context = build_invoice_document_context(invoice, request=request, for_pdf=for_pdf)
    return render_to_string(UNIFIED_TEMPLATE, context, request=request)
