"""
Streamlit Dashboard for Gare Easy
Real-time monitoring and exploration of tender data
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Optional import for Plotly
try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager
from database.models import Tender, Level2Data, Attachment, ScraperLog
import yaml


# Page configuration
st.set_page_config(
    page_title="Gare Easy - Tender Dashboard",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_resource
def get_db_manager():
    """Initialize database manager"""
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    db_path = config['database']['path']
    return DatabaseManager(f"sqlite:///{db_path}")


@st.cache_data(ttl=60)
def get_statistics(_db_manager):
    """Get overall statistics"""
    return _db_manager.get_statistics()


@st.cache_data(ttl=60)
def get_tenders_df(_db_manager, status_filter=None, platform_filter=None):
    """Get tenders as DataFrame with full Level 2 details"""
    with _db_manager.get_session() as session:
        query = session.query(Tender)
        
        if status_filter and status_filter != 'All':
            query = query.filter(Tender.status == status_filter)
        
        if platform_filter and platform_filter != 'All':
            query = query.filter(Tender.platform_name == platform_filter)
        
        # Eager load Level 2 data to avoid N+1 queries
        from sqlalchemy.orm import joinedload
        query = query.options(joinedload(Tender.level2_data))
        tenders = query.order_by(Tender.deadline.desc()).all()
        
        data = []
        for t in tenders:
            l2 = t.level2_data
            
            row = {
                'Title': t.title,
                'Amount': t.amount,
                'Type of procedure': t.procedure_type,
                'Tender category': t.category,
                'Place of execution': t.place_of_execution,
                'Contracting authority (SA)': t.contracting_authority,
                'Tender platform': t.platform_name,
                'CPV': t.cpv_codes,
                'Publication date': t.publication_date,
                'Last update date': t.last_updated_at.date() if t.last_updated_at else None,
                'Deadline': t.deadline,
                'Sector type': t.sector_type,
                'Platform link': t.url,
                'Evaluation date': t.evaluation_date,
                'Award criterion': t.award_criterion,
                'CIG': t.id,
                'Contract duration': t.contract_duration,
                'Number of lots': t.num_lots,
                'Email': t.email,
                'RUP': t.rup_name,
                'Required qualifications': l2.required_qualifications if l2 else None,
                'Evaluation criteria': l2.evaluation_criteria if l2 else None,
                'Tender process description': l2.process_description if l2 else None,
                'Delivery/execution methods': l2.delivery_methods if l2 else None,
                'Required documentation': l2.required_documentation if l2 else None,
                # Keep internal fields for analytics/filtering
                'Status': t.status,
                'Quality Score': t.data_quality_score
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # Reorder columns to match requested template if DataFrame is not empty
        if not df.empty:
            template_columns = [
                'Title', 'Amount', 'Type of procedure', 'Tender category', 'Place of execution',
                'Contracting authority (SA)', 'Tender platform', 'CPV', 'Publication date',
                'Last update date', 'Deadline', 'Sector type', 'Platform link', 'Evaluation date',
                'Award criterion', 'CIG', 'Contract duration', 'Number of lots', 'Email', 'RUP',
                'Required qualifications', 'Evaluation criteria', 'Tender process description',
                'Delivery/execution methods', 'Required documentation',
                # Internal columns (appended at end)
                'Status', 'Quality Score'
            ]
            # Ensure all columns exist
            for col in template_columns:
                if col not in df.columns:
                    df[col] = None
            
            # Select and reorder
            df = df[template_columns]
            
        return df


def main():
    """Main dashboard"""
    
    # Header
    st.title("📋 Gare Easy - Public Procurement Dashboard")
    st.markdown("*Real-time monitoring of Italian public tenders*")
    st.divider()
    
    # Initialize database
    try:
        db_manager = get_db_manager()
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        st.info("Run `python main.py --init-db` to initialize the database")
        return
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Filters")
        
        # Status filter
        status_options = ['All', 'Active', 'Updated', 'Closed']
        status_filter = st.selectbox("Status", status_options)
        
        # Platform filter
        stats = get_statistics(db_manager)
        platform_options = ['All'] + list(stats['platform_breakdown'].keys())
        platform_filter = st.selectbox("Platform", platform_options)
        
        # Date range
        st.subheader("Deadline Range")
        days_ahead = st.slider("Days ahead", 7, 90, 30)
        
        st.divider()
        
        # Refresh button
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Main content
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📋 Tenders", "📈 Analytics", "🔍 Details"])
    
    with tab1:
        show_overview(db_manager, stats)
    
    with tab2:
        show_tenders_table(db_manager, status_filter, platform_filter)
    
    with tab3:
        show_analytics(db_manager)
    
    with tab4:
        show_tender_details(db_manager)


def show_overview(db_manager, stats):
    """Show overview statistics"""
    st.header("Overview")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Tenders",
            value=stats['total_tenders'],
            delta=None
        )
    
    with col2:
        st.metric(
            label="Active Tenders",
            value=stats['active_tenders'],
            delta=None
        )
    
    with col3:
        st.metric(
            label="Attachments",
            value=stats['total_attachments'],
            delta=f"{stats['downloaded_attachments']} downloaded"
        )
    
    with col4:
        st.metric(
            label="Platforms",
            value=len(stats['platform_breakdown']),
            delta=None
        )
    
    st.divider()
    
    # Platform breakdown
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Tenders by Platform")
        
        if stats['platform_breakdown']:
            platform_df = pd.DataFrame([
                {'Platform': k, 'Count': v}
                for k, v in stats['platform_breakdown'].items()
            ])
            
            if HAS_PLOTLY:
                fig = px.bar(
                    platform_df,
                    x='Platform',
                    y='Count',
                    color='Platform',
                    text='Count'
                )
                fig.update_layout(showlegend=False, height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(platform_df.set_index('Platform'))
        else:
            st.info("No tenders yet")
    
    with col2:
        st.subheader("Recent Activity")
        
        # Get recent scraper logs
        with db_manager.get_session() as session:
            logs = session.query(ScraperLog).order_by(
                ScraperLog.run_start.desc()
            ).limit(5).all()
            
            if logs:
                log_data = []
                for log in logs:
                    log_data.append({
                        'Platform': log.platform_name,
                        'Time': log.run_start.strftime('%Y-%m-%d %H:%M'),
                        'Status': log.status,
                        'New': log.tenders_new,
                        'Updated': log.tenders_updated
                    })
                
                st.dataframe(
                    pd.DataFrame(log_data),
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("No scraper runs yet")


def show_tenders_table(db_manager, status_filter, platform_filter):
    """Show tenders table"""
    st.header("Tenders")
    
    # Get data
    df = get_tenders_df(db_manager, status_filter, platform_filter)
    
    if df.empty:
        st.info("No tenders found. Run the scraper to populate the database.")
        st.code("python main.py --platform mef", language="bash")
        return
    
    # Search
    search = st.text_input("🔍 Search tenders", placeholder="Search by title, authority, or ID...")
    
    if search:
        mask = df.apply(lambda row: search.lower() in str(row).lower(), axis=1)
        df = df[mask]
    
    # Display count
    st.caption(f"Showing {len(df)} tenders")
    
    # Create a copy for display formatting so we don't affect the export
    display_df = df.copy()
    
    # Format amount
    if 'Amount' in display_df.columns:
        display_df['Amount (€)'] = display_df['Amount'].apply(
            lambda x: f"€ {x:,.2f}" if pd.notna(x) else "N/A"
        )
        display_df = display_df.drop('Amount', axis=1)
    
    # Format dates
    if 'Deadline' in display_df.columns:
        display_df['Deadline'] = pd.to_datetime(display_df['Deadline'])
        display_df['Days Until Deadline'] = (display_df['Deadline'] - datetime.now()).dt.days
    
    # Display table
    st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Platform link": st.column_config.LinkColumn("Link"),
            "Quality Score": st.column_config.ProgressColumn(
                "Quality",
                format="%.0f%%",
                min_value=0,
                max_value=100
            ),
            "Deadline": st.column_config.DatetimeColumn(
                "Deadline",
                format="DD/MM/YYYY HH:mm"
            ),
            "Publication date": st.column_config.DateColumn(
                "Published",
                format="DD/MM/YYYY"
            )
        }
    )
    
    # Export
    if not df.empty:
        # Define exact template columns and order
        template_columns = [
            'Title', 'Amount', 'Type of procedure', 'Tender category', 'Place of execution',
            'Contracting authority (SA)', 'Tender platform', 'CPV', 'Publication date',
            'Last update date', 'Deadline', 'Sector type', 'Platform link', 'Evaluation date',
            'Award criterion', 'CIG', 'Contract duration', 'Number of lots', 'Email', 'RUP',
            'Required qualifications', 'Evaluation criteria', 'Tender process description',
            'Delivery/execution methods', 'Required documentation'
        ]
        
        # Select available columns from template, ignoring internal ones
        export_cols = [c for c in template_columns if c in df.columns]
        export_df = df[export_cols]
        
        csv = export_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV (Template Format)",
            data=csv,
            file_name=f"gare_easy_export_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )


def show_analytics(db_manager):
    """Show analytics"""
    st.header("Analytics")
    
    df = get_tenders_df(db_manager)
    
    if df.empty:
        st.info("No data available for analytics")
        return
    
    # Timeline
    st.subheader("Tenders Timeline")
    
    if 'Deadline' in df.columns:
        df['Deadline'] = pd.to_datetime(df['Deadline'])
        df['Month'] = df['Deadline'].dt.to_period('M').astype(str)
        
        timeline = df.groupby(['Month', 'Tender platform']).size().reset_index(name='Count')
        
        fig = px.line(
            timeline,
            x='Month',
            y='Count',
            color='Tender platform',
            markers=True
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    # Category distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("By Category")
        
        if 'Tender category' in df.columns:
            category_counts = df['Tender category'].value_counts()
            
            fig = px.pie(
                values=category_counts.values,
                names=category_counts.index,
                hole=0.4
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("By Status")
        
        if 'Status' in df.columns:
            status_counts = df['Status'].value_counts()
            
            fig = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                hole=0.4
            )
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)


def show_tender_details(db_manager):
    """Show detailed tender information"""
    st.header("Tender Details")
    
    # Get all tender IDs
    with db_manager.get_session() as session:
        tenders = session.query(Tender.id, Tender.title).all()
        
        if not tenders:
            st.info("No tenders available")
            return
        
        # Select tender
        tender_options = {f"{t.id}: {t.title[:50]}...": t.id for t in tenders}
        selected = st.selectbox("Select Tender", options=list(tender_options.keys()))
        
        if not selected:
            return
        
        tender_id = tender_options[selected]
        
        # Get tender details
        tender = session.query(Tender).filter_by(id=tender_id).first()
        
        if not tender:
            st.error("Tender not found")
            return
        
        # Display details
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Basic Information")
            st.write(f"**Title:** {tender.title}")
            st.write(f"**Platform:** {tender.platform_name}")
            st.write(f"**Authority:** {tender.contracting_authority or 'N/A'}")
            st.write(f"**Amount:** € {tender.amount:,.2f}" if tender.amount else "**Amount:** N/A")
            st.write(f"**Category:** {tender.category or 'N/A'}")
            st.write(f"**Status:** {tender.status}")
            
            if tender.url:
                st.link_button("🔗 View on Platform", tender.url)
        
        with col2:
            st.subheader("Dates & Deadlines")
            st.write(f"**Published:** {tender.publication_date or 'N/A'}")
            st.write(f"**Deadline:** {tender.deadline or 'N/A'}")
            st.write(f"**Evaluation:** {tender.evaluation_date or 'N/A'}")
            st.write(f"**Last Updated:** {tender.last_updated_at.strftime('%Y-%m-%d %H:%M')}")
            
            if tender.deadline:
                days_left = (tender.deadline - datetime.now()).days
                if days_left > 0:
                    st.success(f"⏰ {days_left} days remaining")
                else:
                    st.error("⏰ Deadline passed")
        
        # Additional details
        with st.expander("📄 Additional Details"):
            st.write(f"**CIG:** {tender.id}")
            st.write(f"**CPV Codes:** {tender.cpv_codes or 'N/A'}")
            st.write(f"**Procedure Type:** {tender.procedure_type or 'N/A'}")
            st.write(f"**Award Criterion:** {tender.award_criterion or 'N/A'}")
            st.write(f"**Sector:** {tender.sector_type or 'N/A'}")
            st.write(f"**Place of Execution:** {tender.place_of_execution or 'N/A'}")
            st.write(f"**Contract Duration:** {tender.contract_duration or 'N/A'}")
            st.write(f"**Number of Lots:** {tender.num_lots or 'N/A'}")
            st.write(f"**RUP:** {tender.rup_name or 'N/A'}")
            st.write(f"**Email:** {tender.email or 'N/A'}")
        
        # Level 2 data
        level2 = session.query(Level2Data).filter_by(tender_id=tender_id).first()
        
        if level2:
            with st.expander("🤖 AI-Extracted Information (Level 2)"):
                st.write("**Required Qualifications:**")
                st.write(level2.required_qualifications or "Not available")
                
                st.write("**Evaluation Criteria:**")
                st.write(level2.evaluation_criteria or "Not available")
                
                st.write("**Process Description:**")
                st.write(level2.process_description or "Not available")
                
                st.write("**Delivery Methods:**")
                st.write(level2.delivery_methods or "Not available")
                
                st.write("**Required Documentation:**")
                st.write(level2.required_documentation or "Not available")
                
                st.caption(f"Confidence: {level2.confidence_score:.1%}" if level2.confidence_score else "")
        
        # Attachments
        attachments = session.query(Attachment).filter_by(tender_id=tender_id).all()
        
        if attachments:
            with st.expander(f"📎 Attachments ({len(attachments)})"):
                for att in attachments:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"**{att.file_name}**")
                    
                    with col2:
                        st.write(att.category or "Unknown")
                    
                    with col3:
                        if att.downloaded == 1:
                            st.success("✓ Downloaded")
                        elif att.downloaded == -1:
                            st.error("✗ Failed")
                        else:
                            st.info("⏳ Pending")


if __name__ == '__main__':
    main()
