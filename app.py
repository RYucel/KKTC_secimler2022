import pandas as pd
import plotly.graph_objects as go # Use graph_objects
import plotly.utils
import json
import traceback
from flask import Flask, render_template, request, url_for

# --- Configuration ---
CSV_FILE_PATH = 'Adaylar_2022_full.csv'
DEBUG_MODE = True # Set to False for production

# --- Initialize Flask App ---
app = Flask(__name__)

# --- Global variable for DataFrame ---
df_full = None

# --- Function to Load Data (same as before) ---
def load_data():
    global df_full
    print(f"Loading data from {CSV_FILE_PATH}...")
    try:
        # --- (Load data code remains exactly the same as the previous working version) ---
        dtype_spec = {'sandikno': str, 'pusula_sirasi': str}
        df_full = pd.read_csv(CSV_FILE_PATH, dtype=dtype_spec)
        df_full['isim'] = df_full['isim'].astype(str).fillna('')
        df_full['soyisim'] = df_full['soyisim'].astype(str).fillna('')
        df_full['candidate_fullname'] = (df_full['isim'] + ' ' + df_full['soyisim']).str.strip()
        vote_cols = ['toplam_aldigi_oy_sayisi', 'toplam_aldigi_tercih_sayisi', 'toplam_aldigi_karma_oy_sayisi', 'toplam']
        for col in vote_cols:
            if col in df_full.columns:
                df_full[col] = pd.to_numeric(df_full[col], errors='coerce').fillna(0).astype(int)
            else:
                print(f"Warning: Expected vote column '{col}' not found.")
                df_full[col] = 0
        required_cols = ['Bolge', 'parti_adi_kisa', 'candidate_fullname', 'sandikno', 'ilce', 'toplam']
        missing_req_cols = [col for col in required_cols if col not in df_full.columns]
        if missing_req_cols:
            raise ValueError(f"Missing required columns: {', '.join(missing_req_cols)}")
        print(f"Data loaded successfully. Shape: {df_full.shape}")
    except Exception as e:
        print(f"ERROR loading data: {e}\n{traceback.format_exc()}")
        exit()

# --- Load data ONCE at startup ---
load_data()

# --- Flask Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if df_full is None: return "Hata: Veri yüklenemedi.", 500 # TR

    df_filtered = df_full.copy()
    fig = go.Figure() # Initialize with graph_objects
    plot_generated = False
    graphJSON = "{}" # Default empty JSON

    selected_region = request.form.get('region', '')
    selected_party = request.form.get('party', '')
    selected_candidate = request.form.get('candidate', '')
    selected_ballot_box_str = request.form.get('ballot_box', '').strip()

    regions = sorted(df_full['Bolge'].unique())
    parties = sorted(df_full['parti_adi_kisa'].unique())
    candidates = sorted(df_full['candidate_fullname'].dropna().unique())

    # --- Apply Filters (same as before) ---
    try:
        # (Filtering logic remains the same)
        print(f"Filtreleme: Bölge='{selected_region}', Parti='{selected_party}', Aday='{selected_candidate}', Sandık='{selected_ballot_box_str}'") # TR
        initial_rows = len(df_filtered)
        if selected_region: df_filtered = df_filtered[df_filtered['Bolge'] == selected_region]
        if selected_party: df_filtered = df_filtered[df_filtered['parti_adi_kisa'] == selected_party]
        if selected_candidate: df_filtered = df_filtered[df_filtered['candidate_fullname'] == selected_candidate]
        if selected_ballot_box_str:
            if 'sandikno' in df_filtered.columns: df_filtered = df_filtered[df_filtered['sandikno'] == selected_ballot_box_str]
            else: print("Uyarı: Filtreleme için 'sandikno' sütunu bulunamadı.") # TR
        print(f"Filtreleme tamamlandı. Satır sayısı {initial_rows} -> {len(df_filtered)}") # TR
    except Exception as e:
        print(f"Filtreleme sırasında hata: {e}\n{traceback.format_exc()}") # TR
        df_filtered = pd.DataFrame(columns=df_full.columns)

    # --- Aggregation into Summary DataFrames (same as before) ---
    candidate_summary, party_summary, region_summary = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    if not df_filtered.empty:
        try:
            candidate_summary = df_filtered.groupby(['parti_adi_kisa', 'candidate_fullname'])['toplam'].sum().reset_index().sort_values('toplam', ascending=False)
            party_summary = df_filtered.groupby('parti_adi_kisa')['toplam'].sum().reset_index().sort_values('toplam', ascending=False)
            region_summary = df_filtered.groupby('Bolge')['toplam'].sum().reset_index().sort_values('toplam', ascending=False)
        except Exception as e:
            print(f"Özetleme sırasında hata: {e}\n{traceback.format_exc()}") # TR


    # --- Conditional Chart Generation using plotly.graph_objects ---
    # --- TRANSLATED TITLES ---
    chart_title = "Oy Özeti Grafiği" # Default title TR
    plot_data_used = "Yok" # TR
    xaxis_title = "Kategori" # TR Generic
    yaxis_title = "Toplam Oylar" # TR Generic

    try:
        # Case 1: Candidate Filtered -> Show Votes per Region for Candidate
        if selected_candidate:
            if not region_summary.empty and region_summary['toplam'].sum() > 0:
                plot_data_used = "Bölge Özeti (Aday için)" # TR
                chart_title = f"{selected_candidate} İçin Bölge Bazında Oylar" # TR
                xaxis_title = "Bölge" # TR
                fig.add_trace(go.Bar(x=region_summary['Bolge'].tolist(), y=region_summary['toplam'].tolist(), name='Oylar', orientation='v')) # TR
                fig.update_xaxes(categoryorder="array", categoryarray=region_summary['Bolge'].tolist())
                plot_generated = True

        # Case 2: Party Filtered (but NOT Candidate) -> Show Top Candidates for Party
        elif selected_party:
            if not candidate_summary.empty and candidate_summary['toplam'].sum() > 0:
                plot_data_used = "Aday Özeti (Parti için)" # TR
                top_n_candidates = 30
                plot_df = candidate_summary[candidate_summary['parti_adi_kisa'] == selected_party].head(top_n_candidates)
                if not plot_df.empty:
                    chart_title = f"{selected_party} İçin İlk {len(plot_df)} Aday (Filtrelenmiş)" # TR
                    xaxis_title = "Aday" # TR
                    print(f"DEBUG: Plotting Candidate Summary for Party: {selected_party}") # Keep debug eng
                    print(plot_df[['candidate_fullname', 'toplam']].head())
                    fig.add_trace(go.Bar(x=plot_df['candidate_fullname'].tolist(), y=plot_df['toplam'].tolist(), name='Oylar', orientation='v')) # TR
                    fig.update_xaxes(categoryorder="array", categoryarray=plot_df['candidate_fullname'].tolist())
                    plot_generated = True
                else:
                    print(f"DEBUG: No candidates found for party '{selected_party}' after aggregation/filtering for chart.") # Keep debug eng

        # Case 3: Ballot Box Filtered (and NOT Candidate/Party) -> Show Parties in Box
        elif selected_ballot_box_str:
             if not party_summary.empty and party_summary['toplam'].sum() > 0:
                plot_data_used = "Parti Özeti (Sandık için)" # TR
                chart_title = f"{selected_ballot_box_str} Nolu Sandıkta Parti Bazında Oylar" # TR
                xaxis_title = "Parti" # TR
                fig.add_trace(go.Bar(x=party_summary['parti_adi_kisa'].tolist(), y=party_summary['toplam'].tolist(), name='Oylar', orientation='v')) # TR
                fig.update_xaxes(categoryorder="array", categoryarray=party_summary['parti_adi_kisa'].tolist())
                plot_generated = True

        # Case 4: Only Region Filtered or No Filters -> Show Parties overall/in Region
        else:
            if not party_summary.empty and party_summary['toplam'].sum() > 0:
                plot_data_used = "Parti Özeti (Bölge/Genel)" # TR
                chart_title = "Parti Bazında Toplam Oylar (Filtrelenmiş)" # TR
                xaxis_title = "Parti" # TR
                if selected_region:
                    chart_title = f"{selected_region} Bölgesinde Parti Bazında Toplam Oylar" # TR
                fig.add_trace(go.Bar(x=party_summary['parti_adi_kisa'].tolist(), y=party_summary['toplam'].tolist(), name='Toplam Oylar', orientation='v')) # TR
                fig.update_xaxes(categoryorder="array", categoryarray=party_summary['parti_adi_kisa'].tolist())
                plot_generated = True


        # --- Common Plot Updates ---
        if plot_generated:
            print(f"DEBUG: Plot generated based on: {plot_data_used}") # Keep debug eng
            fig.update_layout(
                title_text=chart_title,
                title_x=0.5,
                xaxis_title=xaxis_title, # Use dynamic title
                yaxis_title=yaxis_title, # Use dynamic title
                xaxis_tickangle=-45,
                yaxis_type='linear'
            )
        else:
             # Fallback/Placeholder logic
             placeholder_title = "Grafik için filtre seçin veya veri yok." # TR
             if fig.data: fig.data = []
             fig.update_layout(title_text=placeholder_title, title_x=0.5, xaxis={'visible': False}, yaxis={'visible': False}, annotations=[])


    except Exception as e:
        print(f"Grafik oluşturma hatası: {e}\n{traceback.format_exc()}") # TR
        plot_generated = False
        fig = go.Figure() # Ensure fig exists on error
        fig.update_layout(title_text="Grafik oluşturulurken hata oluştu", title_x=0.5, xaxis={'visible': False}, yaxis={'visible': False}) # TR


    # --- Convert Plot to JSON ---
    try:
        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    except Exception as e:
        print(f"Plotly figürünü JSON'a dökerken hata: {e}\n{traceback.format_exc()}") # TR
        error_fig = go.Figure()
        error_fig.update_layout(title_text="Grafik verisi hazırlanırken hata.", title_x=0.5, xaxis={'visible': False}, yaxis={'visible': False}) # TR
        graphJSON = json.dumps(error_fig, cls=plotly.utils.PlotlyJSONEncoder)


    # --- Prepare Summary Tables HTML ---
    # --- TRANSLATED "No Data" Messages ---
    no_candidate_summary_msg = "<p class='text-center text-muted mt-3'>Filtreler için aday özeti verisi yok.</p>" # TR
    no_party_summary_msg = "<p class='text-center text-muted mt-3'>Filtreler için parti özeti verisi yok.</p>" # TR
    no_region_summary_msg = "<p class='text-center text-muted mt-3'>Filtreler için bölge özeti verisi yok.</p>" # TR

    candidate_summary_html = no_candidate_summary_msg
    party_summary_html = no_party_summary_msg
    region_summary_html = no_region_summary_msg

    if not candidate_summary.empty: candidate_summary_html = candidate_summary.head(50).to_html(classes='table table-bordered table-hover table-sm', index=False, border=0, na_rep='-')
    if not party_summary.empty: party_summary_html = party_summary.to_html(classes='table table-bordered table-hover table-sm', index=False, border=0, na_rep='-')
    if not region_summary.empty: region_summary_html = region_summary.to_html(classes='table table-bordered table-hover table-sm', index=False, border=0, na_rep='-')


    # --- Prepare Raw Data Table ---
    no_raw_data_msg = "<p class='text-center text-muted mt-3'>Seçili filtrelere uygun ham veri bulunamadı.</p>" # TR
    display_cols = ['Bolge', 'sandikno', 'parti_adi_kisa', 'candidate_fullname', 'ilce', 'toplam_aldigi_oy_sayisi', 'toplam_aldigi_tercih_sayisi', 'toplam_aldigi_karma_oy_sayisi', 'toplam']
    display_cols_present = [col for col in display_cols if col in df_filtered.columns]
    table_df = df_filtered[display_cols_present].head(100)
    raw_table_html = table_df.to_html(classes='table table-striped table-hover table-sm', index=False, border=0, na_rep='-') if not table_df.empty else no_raw_data_msg
    total_results_count = len(df_filtered)

    # --- Render Template ---
    return render_template('index.html',
                           regions=regions, parties=parties, candidates=candidates,
                           selected_region=selected_region, selected_party=selected_party, selected_candidate=selected_candidate, selected_ballot_box=selected_ballot_box_str,
                           graphJSON=graphJSON,
                           candidate_summary_html=candidate_summary_html, party_summary_html=party_summary_html, region_summary_html=region_summary_html,
                           raw_table_html=raw_table_html, total_results_count=total_results_count
                           )

# --- Run the App ---
if __name__ == '__main__':
    if df_full is not None: print("Flask sunucusu başlatılıyor..."); app.run(debug=DEBUG_MODE) # TR
    else: print("Veri yüklemesi başarısız olduğu için uygulama başlatılamıyor.") # TR