/**
 * Easy 66 & Co — Pure Clean Language Switcher (தமிழ் அல்லது ஆங்கிலம் மட்டும்)
 * Strict Single Language: Never mixed or cluttered!
 */

const DICT = {
  // Brand & Nav
  'brand_title': { en: 'Easy 66 & Co', ta: 'ஈசி 66 & கோ' },
  'thavanai_concept': { en: 'Thavanai Finance', ta: 'தவணை முறை' },
  'nav_dashboard': { en: 'Dashboard', ta: 'முகப்பு பலகை' },
  'nav_customers': { en: 'Customers', ta: 'வாடிக்கையாளர்கள்' },
  'nav_loans': { en: 'Loans', ta: 'கடன்கள்' },
  'nav_loan_requests': { en: 'Loan Requests', ta: 'கடன் விண்ணப்பங்கள்' },
  'nav_collections': { en: 'Collections', ta: 'வசூல் விவரம்' },
  'nav_whatsapp': { en: 'WhatsApp', ta: 'வாட்ஸ்அப்' },
  'nav_inquiries': { en: 'Inquiries', ta: 'விவர தேடல்' },
  'nav_reports': { en: 'Reports', ta: 'அறிக்கைகள்' },
  'nav_staff': { en: 'Staff', ta: 'பணியாளர்கள்' },
  'nav_cashfree': { en: 'Cashfree AutoPay', ta: 'கேஷ்ஃப்ரீ தானியங்கி' },
  'lbl_mandate_status': { en: 'Mandate Status', ta: 'ஒப்புதல் நிலை' },
  'btn_setup_mandate': { en: 'Set Up AutoPay', ta: 'தானியங்கி தவணை அமை' },
  'nav_logout': { en: 'Logout', ta: 'வெளியேறு' },

  // Dashboard Stats
  'lbl_total_customers': { en: 'Total Customers', ta: 'மொத்த வாடிக்கையாளர்கள்' },
  'lbl_total_loans': { en: 'Total Loans', ta: 'மொத்த கடன்கள்' },
  'lbl_total_gross': { en: 'Total Gross Principal', ta: 'மொத்த தவணைத் தொகை' },
  'lbl_total_disbursed': { en: 'Cash Disbursed', ta: 'கையில் கொடுத்த தொகை' },
  'lbl_upfront_interest': { en: 'Upfront Interest', ta: 'பிடித்தம் செய்த வட்டி' },
  'lbl_total_collected': { en: 'Total Collected', ta: 'மொத்த வசூல்' },
  'lbl_collected_today': { en: 'Collected Today', ta: 'இன்றைய வசூல்' },
  'lbl_pending_overdue': { en: 'Pending / Overdue', ta: 'நிலுவை / காலாவதி' },
  'lbl_overdue': { en: 'Overdue', ta: 'காலாவதியானது' },
  'lbl_active': { en: 'Active', ta: 'நடப்பில்' },
  'lbl_completed': { en: 'Completed', ta: 'முடிந்தது' },
  'lbl_defaulted': { en: 'Defaulted', ta: 'தவறியது' },
  'lbl_expected': { en: 'Expected', ta: 'எதிர்பார்க்கும் தொகை' },

  // Collections Page Specific
  'lbl_today_coll': { en: "Today's Collection", ta: 'இன்றைய வசூல்' },
  'lbl_week_coll': { en: 'This Week', ta: 'இந்த வாரம்' },
  'lbl_month_coll': { en: 'This Month', ta: 'இந்த மாதம்' },
  'lbl_all_time_coll': { en: 'All-Time Collected', ta: 'மொத்த வசூல் தொகை' },
  'lbl_filtered_total': { en: 'Filtered Total', ta: 'வடிகட்டிய தொகை' },
  'lbl_collection_records': { en: 'Collection Records', ta: 'வசூல் பதிவுகள்' },
  'lbl_collected_by': { en: 'Collected By', ta: 'வசூலித்தவர்' },

  // Inquiry & Estimation Specific
  'inquiry_title': { en: 'Loan Inquiry & Estimation', ta: 'கடன் விசாரணை & உத்தேச கணக்கீடு' },
  'inquiry_subtitle': { en: 'Instant Thavanai loan estimation without creating a customer record.', ta: 'வாடிக்கையாளர் கணக்கு தொடங்காமல் உடனுக்குடன் தவணை கடன் உத்தேச கணக்கீடு.' },
  'lbl_quick_presets': { en: 'Quick Amount Presets', ta: 'விரைவு தொகை தேர்வுகள்' },
  'lbl_loan_inputs': { en: 'Estimation Parameters', ta: 'உத்தேச கடன் அளவீடுகள்' },
  'lbl_projected_schedule': { en: 'Projected Repayment Schedule', ta: 'உத்தேச திருப்பிச் செலுத்தும் அட்டவணை' },
  'lbl_projected_end': { en: 'Projected End Date', ta: 'கடன் முடியும் தேதி' },
  'lbl_tenure': { en: 'Tenure', ta: 'கால அளவு' },
  'lbl_total_repayment': { en: 'Total Repayment', ta: 'மொத்த திருப்பிச் செலுத்துதல்' },
  'btn_estimate_now': { en: 'Calculate Estimation', ta: 'உத்தேச கணக்கீடு செய்' },
  'btn_issue_this_loan': { en: 'Issue This Loan', ta: 'இந்த கடனை வழங்குக' },
  'btn_download_quotation': { en: 'Quotation PDF', ta: 'விலைப்புள்ளி PDF' },
  'lbl_show_all_inst': { en: 'Show All Installments', ta: 'அனைத்து தவணைகளையும் காட்டு' },
  'lbl_show_less': { en: 'Show Less', ta: 'குறைவாகக் காட்டு' },
  'th_cum_paid': { en: 'Cumulative Paid', ta: 'செலுத்திய மொத்த தொகை' },
  'th_rem_bal': { en: 'Remaining Balance', ta: 'மீதமுள்ள அசல்' },

  // Sections
  'sec_upcoming_collections': { en: 'Upcoming Collections (Next 7 Days)', ta: 'அடுத்த 7 நாள் தவணைகள்' },
  'sec_recent_collections': { en: 'Recent Collections', ta: 'சமீபத்திய வசூல்கள்' },
  'sec_collection_analytics': { en: 'Collection Analytics (Last 6 Months)', ta: 'மாதாந்திர வசூல் விவரம்' },
  'sec_loan_status': { en: 'Loan Status Breakdown', ta: 'கடன் நிலை விவரம்' },
  'sec_installments_schedule': { en: 'Installment Repayment Schedule', ta: 'தவணை பட்டியல் விவரம்' },

  // Form Labels
  'lbl_cust_name': { en: 'Customer Full Name', ta: 'வாடிக்கையாளர் பெயர்' },
  'lbl_phone': { en: 'Phone Number', ta: 'தொலைபேசி எண்' },
  'lbl_email': { en: 'Email Address', ta: 'மின்னஞ்சல்' },
  'lbl_address': { en: 'Address', ta: 'முகவரி' },
  'lbl_select_existing': { en: 'Select Existing Customer', ta: 'வாடிக்கையாளரை தேர்ந்தெடுக்கவும்' },
  'lbl_existing_cust_tab': { en: 'Existing Customer', ta: 'பழைய வாடிக்கையாளர்' },
  'lbl_new_cust_tab': { en: 'New Customer', ta: 'புதிய வாடிக்கையாளர்' },
  'lbl_gross_principal': { en: 'Gross Principal (₹)', ta: 'மொத்த தவணைத் தொகை (₹)' },
  'lbl_upfront_interest_pct': { en: 'Upfront Interest Rate (%)', ta: 'முன்பண வட்டி (%)' },
  'lbl_cash_disbursed': { en: 'Cash Disbursed (Net ₹)', ta: 'கையில் கொடுக்கும் தொகை (₹)' },
  'lbl_frequency': { en: 'Collection Frequency', ta: 'தவணை முறை' },
  'lbl_installment_count': { en: 'Total Installments', ta: 'தவணைகள் எண்ணிக்கை' },
  'lbl_installment_amount': { en: 'Per Installment Amount', ta: 'ஒரு தவணைத் தொகை' },
  'lbl_start_date': { en: 'Start Date', ta: 'தொடங்கும் தேதி' },
  'lbl_assign_staff': { en: 'Assign to Staff', ta: 'பணியாளரை நியமி' },
  'lbl_status': { en: 'Loan Status', ta: 'கடன் நிலை' },
  'lbl_thavanai_calc_title': { en: 'Thavanai Calculation', ta: 'தவணை கடன் கணக்கீடு' },
  'lbl_thavanai_calc_sub': { en: 'Upfront interest and net cash are calculated automatically.', ta: 'முன்பண வட்டியும் கையில் கொடுக்கும் தொகையும் தானாக கணக்கிடப்படும்.' },

  // Table Headers
  'th_id': { en: 'ID', ta: 'எண்' },
  'th_loan_id': { en: 'Loan ID', ta: 'கடன் எண்' },
  'th_customer': { en: 'Customer', ta: 'வாடிக்கையாளர்' },
  'th_phone': { en: 'Phone', ta: 'தொலைபேசி' },
  'th_gross': { en: 'Gross', ta: 'மொத்த தொகை' },
  'th_net_cash': { en: 'Cash Given', ta: 'கையில் கொடுத்தது' },
  'th_frequency': { en: 'Frequency', ta: 'முறை' },
  'th_per_inst': { en: 'Per Inst', ta: 'தவணை தொகை' },
  'th_installments': { en: 'Installments', ta: 'தவணைகள்' },
  'th_due_date': { en: 'Due Date', ta: 'தவணை தேதி' },
  'th_paid_date': { en: 'Paid Date', ta: 'செலுத்திய தேதி' },
  'th_amount': { en: 'Amount', ta: 'தொகை' },
  'th_paid': { en: 'Paid', ta: 'செலுத்தியது' },
  'th_outstanding': { en: 'Outstanding', ta: 'நிலுவை' },
  'th_balance': { en: 'Balance', ta: 'மீதம்' },
  'th_status': { en: 'Status', ta: 'நிலை' },
  'th_staff': { en: 'Staff', ta: 'பணியாளர்' },
  'th_actions': { en: 'Actions', ta: 'செயல்கள்' },

  // Buttons
  'btn_collect': { en: 'Collect', ta: 'வசூலி' },
  'btn_create_loan': { en: 'Create Loan', ta: 'கடன் வழங்குக' },
  'btn_add_customer': { en: 'Add Customer', ta: 'வாடிக்கையாளர் சேர்' },
  'btn_add_staff': { en: 'Add Staff', ta: 'பணியாளர் சேர்' },
  'btn_view_details': { en: 'View Details', ta: 'விவரம் பார்' },
  'btn_view_all_details': { en: 'Click to view all details →', ta: 'அனைத்து விவரங்களையும் பார்க்க →' },
  'btn_edit': { en: 'Edit', ta: 'திருத்து' },
  'btn_delete': { en: 'Delete', ta: 'நீக்கு' },
  'btn_settle_all': { en: 'Settle Full Balance', ta: 'முழுத் தொகையை முடி' },
  'btn_download_pdf': { en: 'Download as PDF', ta: 'PDF பதிவிறக்கு' },
  'btn_search': { en: 'Search', ta: 'தேடு' },
  'btn_filter': { en: 'Filter', ta: 'வடிகட்டு' },
  'btn_cancel': { en: 'Cancel', ta: 'ரத்து' },
  'btn_save': { en: 'Save Customer', ta: 'வாடிக்கையாளரை சேமி' },
  'btn_save_loan': { en: 'Issue & Save Loan', ta: 'கடனை உறுதிசெய்' },
  'btn_save_staff': { en: 'Save Staff', ta: 'பணியாளரை சேமி' },
  'btn_back': { en: 'Back', ta: 'திரும்பு' },
  'btn_full_report': { en: 'Full Report', ta: 'முழு அறிக்கை' },

  // Placeholders
  'ph_search_global': { en: 'Search customer, phone, ID...', ta: 'வாடிக்கையாளர், தொலைபேசி, எண் தேடு...' },
  'ph_name': { en: 'Enter customer name', ta: 'வாடிக்கையாளர் பெயர் உள்ளிடவும்' },
  'ph_phone': { en: 'Enter phone number', ta: 'தொலைபேசி எண் உள்ளிடவும்' },
  'ph_email': { en: 'Enter email address (optional)', ta: 'மின்னஞ்சல் உள்ளிடவும் (விருப்பப்பட்டால்)' },
  'ph_address': { en: 'Enter full address', ta: 'முழு முகவரியை உள்ளிடவும்' },
  'ph_staff_name': { en: 'Enter full name', ta: 'முழு பெயரை உள்ளிடவும்' },
  'ph_username': { en: 'Enter username', ta: 'பயனர் பெயரை உள்ளிடவும்' },
  'ph_password': { en: 'Enter password', ta: 'கடவுச்சொல்லை உள்ளிடவும்' },

  // Frequency names
  'freq_daily': { en: 'Daily', ta: 'தினசரி' },
  'freq_weekly': { en: 'Weekly', ta: 'வாராந்திர' },
  'freq_monthly': { en: 'Monthly', ta: 'மாதாந்திர' },

  // Reports
  'lbl_report_type': { en: 'Report Type', ta: 'அறிக்கை வகை' },
  'lbl_from_date': { en: 'From Date', ta: 'தொடக்க தேதி' },
  'lbl_to_date': { en: 'To Date', ta: 'முடிவு தேதி' },
  'rpt_summary': { en: 'Overall Summary Report', ta: 'முழு சுருக்க அறிக்கை' },
  'rpt_collection': { en: 'Collection Report', ta: 'வசூல் அறிக்கை' },
  'rpt_outstanding': { en: 'Outstanding Balance Report', ta: 'நிலுவைத் தொகை அறிக்கை' },
  'rpt_overdue': { en: 'Overdue Installments Report', ta: 'காலாவதியான தவணைகள் அறிக்கை' },
  'rpt_customer': { en: 'Customer-wise Ledger', ta: 'வாடிக்கையாளர் அறிக்கை' },
};

function getLanguage() {
  return localStorage.getItem('e66_lang') || 'en';
}

function setLanguage(lang) {
  localStorage.setItem('e66_lang', lang);
  applyLanguage(lang);
}

function toggleLanguage() {
  const current = getLanguage();
  const next = current === 'en' ? 'ta' : 'en';
  setLanguage(next);
}

function applyLanguage(lang) {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (DICT[key] && DICT[key][lang]) {
      el.textContent = DICT[key][lang];
    }
  });

  document.querySelectorAll('[data-i18n-ph]').forEach(el => {
    const key = el.getAttribute('data-i18n-ph');
    if (DICT[key] && DICT[key][lang]) {
      el.setAttribute('placeholder', DICT[key][lang]);
    }
  });

  const freqSelect = document.getElementById('id_frequency');
  if (freqSelect) {
    for (let opt of freqSelect.options) {
      if (opt.value === 'daily') opt.text = lang === 'ta' ? 'தினசரி' : 'Daily';
      else if (opt.value === 'weekly') opt.text = lang === 'ta' ? 'வாராந்திர' : 'Weekly';
      else if (opt.value === 'monthly') opt.text = lang === 'ta' ? 'மாதாந்திர' : 'Monthly';
    }
  }

  const toggleBtn = document.getElementById('langToggleBtn');
  if (toggleBtn) {
    if (lang === 'ta') {
      toggleBtn.innerHTML = '<span class="lang-pill active">தமிழ்</span> <span class="lang-pill">EN</span>';
    } else {
      toggleBtn.innerHTML = '<span class="lang-pill">தமிழ்</span> <span class="lang-pill active">EN</span>';
    }
  }

  if (typeof recalculateThavanai === 'function') {
    recalculateThavanai();
  }

  document.documentElement.lang = lang === 'ta' ? 'ta' : 'en';
}

document.addEventListener('DOMContentLoaded', () => {
  applyLanguage(getLanguage());
});
