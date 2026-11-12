<script lang="ts">
	import type { Signatory } from '$lib/api/types';
	import { mediaUrl } from '$lib/api/client';

	export let invoiceNumber: string = 'INV-XXXXXX';
	export let issueDate: string = '';
	export let dueDate: string = '';
	export let periodStart: string = '';
	export let periodEnd: string = '';
	export let currency: string = 'XAF';
	export let tenantName: string = '';
	export let unitName: string = '';
	export let propertyName: string = '';
	export let lines: { line_type: string; description: string; quantity?: number | string; unit_price?: number | string; amount: number | string }[] = [];
	export let totalAmount: number | string = 0;
	export let notes: string = '';

	// Company info
	export let companyName: string = '';
	export let companyAddress: string = '';
	export let companyCity: string = '';
	export let companyPhone: string = '';
	export let companyEmail: string = '';
	export let companyLogoUrl: string | null = null;
	export let companyBankAccounts: { bank_name: string; account_number: string }[] = [];
	export let companyRccm: string = '';
	export let companyNif: string = '';

	// PDF display preferences
	export let pdfShowRccm: boolean = true;
	export let pdfShowNif: boolean = true;
	export let pdfBankDisplay: 'none' | 'all' | 'selected' = 'all';
	export let pdfSelectedBankIndices: number[] = [];
	export let pdfSignatory: Signatory | null = null;

	const CURRENCY_LABELS: Record<string, string> = { XAF: 'FCFA', XOF: 'FCFA' };

	function currencyLabel(code: string): string {
		return CURRENCY_LABELS[code] || code;
	}

	function fmtAmount(val: number | string): string {
		let num: number;
		if (typeof val === 'string') {
			num = parseFloat(val.replace(/\s/g, ''));
		} else {
			num = val;
		}
		if (isNaN(num)) return String(val);
		// Always round to integer (no decimals)
		num = Math.round(num);
		return num.toLocaleString('fr-FR', { useGrouping: true, maximumFractionDigits: 0 }).replace(/\u202F/g, ' ');
	}

	function fmtDateLong(dateStr: string): string {
		if (!dateStr) return '—';
		const MONTHS = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
			'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
		try {
			const d = new Date(dateStr);
			if (isNaN(d.getTime())) return dateStr;
			return `${d.getDate()} ${MONTHS[d.getMonth() + 1]} ${d.getFullYear()}`;
		} catch {
			return dateStr;
		}
	}

	function amountInWordsFr(amount: number | string): string {
		let n: number;
		if (typeof amount === 'string') {
			n = Math.floor(parseFloat(amount.replace(/\s/g, '')));
		} else {
			n = Math.floor(amount);
		}
		if (isNaN(n) || n === 0) return 'ZÉRO';

		const ones = ['', 'UN', 'DEUX', 'TROIS', 'QUATRE', 'CINQ', 'SIX', 'SEPT',
			'HUIT', 'NEUF', 'DIX', 'ONZE', 'DOUZE', 'TREIZE', 'QUATORZE',
			'QUINZE', 'SEIZE', 'DIX-SEPT', 'DIX-HUIT', 'DIX-NEUF'];
		const tens = ['', '', 'VINGT', 'TRENTE', 'QUARANTE', 'CINQUANTE',
			'SOIXANTE', 'SOIXANTE', 'QUATRE-VINGT', 'QUATRE-VINGT'];

		function under100(n: number): string {
			if (n < 20) return ones[n];
			if (n < 70) {
				const t = Math.floor(n / 10), u = n % 10;
				if (u === 1) return `${tens[t]} ET UN`;
				return u ? `${tens[t]}-${ones[u]}` : tens[t];
			}
			if (n < 80) {
				const u = n - 60;
				if (u === 11) return 'SOIXANTE ET ONZE';
				return `SOIXANTE-${ones[u]}`;
			}
			const u = n - 80;
			if (u === 0) return 'QUATRE-VINGTS';
			return u < 20 ? `QUATRE-VINGT-${ones[u]}` : `QUATRE-VINGT-${under100(u)}`;
		}

		function under1000(n: number, stripPlural = false): string {
			if (n < 100) return under100(n);
			const h = Math.floor(n / 100), r = n % 100;
			if (h === 1) return r ? `CENT ${under100(r)}` : 'CENT';
			const prefix = `${ones[h]} CENT`;
			if (r === 0) return stripPlural ? prefix : `${prefix}S`;
			return `${prefix} ${under100(r)}`;
		}

		const parts: string[] = [];
		let rem = n;
		const billions = Math.floor(rem / 1_000_000_000); rem %= 1_000_000_000;
		const millions = Math.floor(rem / 1_000_000); rem %= 1_000_000;
		const thousands = Math.floor(rem / 1_000); rem %= 1_000;

		if (billions) parts.push(`${under1000(billions, true)} MILLIARD${billions > 1 ? 'S' : ''}`);
		if (millions) parts.push(`${under1000(millions, true)} MILLION${millions > 1 ? 'S' : ''}`);
		if (thousands) parts.push(thousands === 1 ? 'MILLE' : `${under1000(thousands, true)} MILLE`);
		if (rem) parts.push(under1000(rem));

		return parts.join(' ');
	}

	// Computed
	$: cur = currencyLabel(currency);

	$: visibleBanks = (() => {
		if (pdfBankDisplay === 'none') return [];
		if (pdfBankDisplay === 'selected') {
			return companyBankAccounts.filter((_, i) => pdfSelectedBankIndices.includes(i));
		}
		return companyBankAccounts;
	})();

	$: effectiveRccm = pdfShowRccm ? companyRccm : '';
	$: effectiveNif = pdfShowNif ? companyNif : '';

	$: signatoryTitle = pdfSignatory?.label ?? '';

	$: signatoryName = pdfSignatory?.name?.trim() ?? '';

	$: totalInWords = amountInWordsFr(totalAmount);
</script>

<div id="invoice-preview" class="mx-auto bg-white" style="width: 595px; min-height: 842px; font-family: 'Segoe UI', system-ui, sans-serif; position: relative;">
	<!-- Top accent bar -->

	<div style="padding: 32px 40px 120px 40px;">
		<!-- Header: Company + Invoice info -->
		<table style="width: 100%; border-collapse: collapse;">
			<tr>
				<!-- Company info -->
				<td style="vertical-align: top; width: 55%;">
					{#if companyLogoUrl}
						<img src={companyLogoUrl} alt="Logo" style="max-width: 120px; max-height: 50px; display: block; margin-bottom: 12px;" />
					{:else}
						<!-- No logo uploaded: a neutral monogram, not a decorative icon. -->
						<div style="width: 44px; height: 44px; border: 1px solid #cbd5e1; color: #475569; text-align: center; line-height: 42px; font-size: 18px; font-weight: 600; margin-bottom: 12px;">{(companyName || 'S').trim().charAt(0).toUpperCase()}</div>
					{/if}
					<div style="font-size: 16px; font-weight: 700; color: #111827; margin-bottom: 4px;">{companyName || 'Votre Société'}</div>
					<div style="font-size: 11px; color: #6b7280; line-height: 1.6;">
						{companyAddress || '—'}<br>
						{companyCity || '—'}
						{#if companyPhone}<br>{companyPhone}{/if}
						{#if companyEmail}<br>{companyEmail}{/if}
					</div>
				</td>

				<!-- Invoice details -->
				<td style="vertical-align: top; text-align: right; width: 45%;">
					<div style="font-size: 19px; font-weight: 700; color: #031927; letter-spacing: 1.5px; margin-bottom: 8px;">FACTURE</div>
					<table style="margin-left: auto; border-collapse: collapse;">
						<tr>
							<td style="font-size: 11px; color: #6b7280; padding: 3px 12px 3px 0; text-align: left;">N° Facture</td>
							<td style="font-size: 11px; font-weight: 600; color: #111827; padding: 3px 0; text-align: right;">{invoiceNumber}</td>
						</tr>
						<tr>
							<td style="font-size: 11px; color: #6b7280; padding: 3px 12px 3px 0; text-align: left;">Date</td>
							<td style="font-size: 11px; font-weight: 600; color: #111827; padding: 3px 0; text-align: right;">{fmtDateLong(issueDate) || '—'}</td>
						</tr>
						<tr>
							<td style="font-size: 11px; color: #6b7280; padding: 3px 12px 3px 0; text-align: left;">Échéance</td>
							<td style="font-size: 11px; font-weight: 600; color: #111827; padding: 3px 0; text-align: right;">{fmtDateLong(dueDate) || '—'}</td>
						</tr>
					</table>
				</td>
			</tr>
		</table>

		<!-- Divider -->
		<div style="border-top: 1px solid #e5e7eb; margin: 20px 0;"></div>

		<!-- Bill To + Period -->
		<table style="width: 100%; border-collapse: collapse;">
			<tr>
				<td style="vertical-align: top; width: 55%;">
					<div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #9ca3af; margin-bottom: 6px;">Facturé à</div>
					<div style="font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 2px;">{tenantName || '—'}</div>
					<div style="font-size: 11px; color: #6b7280; line-height: 1.6;">
						{propertyName || '—'}<br>
						{unitName || '—'}
					</div>
				</td>
				<td style="vertical-align: top; text-align: right; width: 45%;">
					<div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #9ca3af; margin-bottom: 6px;">Période</div>
					<div style="font-size: 12px; font-weight: 600; color: #374151;">
						{fmtDateLong(periodStart) || '—'} — {fmtDateLong(periodEnd) || '—'}
					</div>
				</td>
			</tr>
		</table>

		<!-- Line items table -->
		<div style="margin-top: 24px;">
			<table style="width: 100%; border-collapse: collapse;">
				<thead>
					<tr>
						<th style="padding: 8px 12px 7px 12px; font-size: 9px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; text-align: left; border-top: 1px solid #031927; border-bottom: 1px solid #031927; width: 44%;">Description</th>
						<th style="padding: 8px 8px 7px 8px; font-size: 9px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; text-align: center; border-top: 1px solid #031927; border-bottom: 1px solid #031927; width: 8%;">Qté</th>
						<th style="padding: 8px 8px 7px 8px; font-size: 9px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; text-align: right; border-top: 1px solid #031927; border-bottom: 1px solid #031927; width: 24%;">Prix Unit. ({cur})</th>
						<th style="padding: 8px 12px 7px 12px; font-size: 9px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; text-align: right; border-top: 1px solid #031927; border-bottom: 1px solid #031927; width: 24%;">Montant ({cur})</th>
					</tr>
				</thead>
				<tbody>
					{#each lines as line, i}
						<tr style="border-bottom: 1px solid {i === lines.length - 1 ? '#031927' : '#e2e8f0'};">
							<td style="padding: 11px 12px; font-size: 11px; color: #111827; font-weight: 500;">{line.description}</td>
							<td style="padding: 11px 8px; font-size: 11px; color: #6b7280; text-align: center;">{Number(line.quantity ?? 1)}</td>
							<td style="padding: 11px 8px; font-size: 11px; color: #6b7280; text-align: right;">{fmtAmount(line.unit_price ?? line.amount)}</td>
							<td style="padding: 11px 12px; font-size: 11px; color: #111827; font-weight: 600; text-align: right;">{fmtAmount(line.amount)}</td>
						</tr>
					{/each}
					{#if lines.length === 0}
						<tr>
							<td colspan="4" style="padding: 20px 12px; text-align: center; font-size: 11px; color: #9ca3af;">Aucune ligne</td>
						</tr>
					{/if}
				</tbody>
			</table>
		</div>

		<!-- Total -->
		<div style="margin: 14px 0 12px 0;">
			<table style="margin-left: auto; min-width: 280px; border-collapse: collapse; border: 1px solid #e2e8f0;">
				<tr>
					<td style="padding: 12px 16px; font-size: 14px; font-weight: 700; color: #031927; text-transform: uppercase; letter-spacing: 0.8px; text-align: left; background-color: #f1f5f9;">Total</td>
					<td style="padding: 12px 16px; font-size: 19px; font-weight: 700; color: #031927; text-align: right; background-color: #f1f5f9;">{fmtAmount(totalAmount)} {cur}</td>
				</tr>
			</table>
		</div>

		<!-- Amount in words -->
		{#if totalInWords}
			<div style="text-align: right; font-size: 10px; font-style: italic; color: #6b7280; letter-spacing: 0.3px;">
				Arrêtée à la somme de : <strong style="color: #374151;">{totalInWords} {cur}</strong>
			</div>
		{/if}

		<!-- Notes -->
		{#if notes}
			<div style="border-top: 1px solid #e2e8f0; padding: 12px 0 0 0; margin-top: 24px;">
				<div style="font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #9ca3af; margin-bottom: 4px;">Notes</div>
				<div style="font-size: 11px; color: #4b5563; line-height: 1.5;">{notes}</div>
			</div>
		{/if}

		<!-- Bank details (full width) -->
		{#if visibleBanks.length > 0}
			<div style="border-top: 1px solid #e2e8f0; padding: 12px 0 0 0; margin-top: 24px; width: 100%;">
				<div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #9ca3af; margin-bottom: 8px;">Coordonnées bancaires</div>
				{#each visibleBanks as bank}
					<div style="font-size: 11px; color: #374151; margin-bottom: 4px;">
						<strong>{bank.bank_name}</strong> — {bank.account_number}
					</div>
				{/each}
			</div>
		{/if}

		<!-- Signatory (right-aligned) -->
		{#if signatoryTitle}
			<div style="text-align: right; margin-top: 20px; margin-bottom: 16px;">
				<div style="font-size: 12px; color: #6b7280; margin-bottom: 4px;">{signatoryTitle}</div>
				{#if signatoryName}
					<div style="font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 4px;">{signatoryName}</div>
				{/if}
				{#if pdfSignatory?.signature_url}
					<div style="margin-top: 6px;">
						<img src={mediaUrl(pdfSignatory.signature_url)} alt="Signature" style="max-height: 112px; max-width: 320px; object-fit: contain; display: inline-block;" />
					</div>
				{/if}
			</div>
		{/if}

		<!-- Footer (pinned to bottom) -->
		<div style="position: absolute; bottom: 0; left: 40px; right: 40px; border-top: 1px solid #e5e7eb; padding: 16px 0 24px 0; text-align: center; font-size: 10px; color: #9ca3af; line-height: 1.8;">
			<p><strong>{companyName || 'Votre Société'}</strong>{companyAddress ? ' — ' + companyAddress : ''}{companyCity ? ', ' + companyCity : ''}</p>
			{#if companyPhone || companyEmail}
				<p>
					{#if companyPhone}{companyPhone}{/if}
					{#if companyPhone && companyEmail} · {/if}
					{#if companyEmail}{companyEmail}{/if}
				</p>
			{/if}
			{#if effectiveRccm || effectiveNif}
				<p>
					{#if effectiveRccm}RCCM : {effectiveRccm}{/if}
					{#if effectiveRccm && effectiveNif} · {/if}
					{#if effectiveNif}NIF : {effectiveNif}{/if}
				</p>
			{/if}
			<p>Merci pour votre confiance.</p>
		</div>
	</div>
</div>
