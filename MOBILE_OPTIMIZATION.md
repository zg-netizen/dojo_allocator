# Mobile-Optimized Dashboard Configuration

## Streamlit Mobile Configuration

Create `~/.streamlit/config.toml`:

```toml
[server]
port = 8501
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#2E7D32"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"

[client]
showErrorDetails = true
```

## Mobile CSS Optimizations

Add to your Streamlit app:

```python
# Mobile CSS optimizations
st.markdown("""
<style>
    /* Mobile-first responsive design */
    @media screen and (max-width: 768px) {
        .main .block-container {
            padding: 1rem;
        }
        
        .stMetric {
            margin: 0.5rem 0;
        }
        
        .stDataFrame {
            font-size: 0.8rem;
        }
        
        .stButton > button {
            width: 100%;
            margin: 0.25rem 0;
        }
        
        .stSelectbox, .stTextInput {
            width: 100%;
        }
        
        /* Touch-friendly buttons */
        .stButton > button {
            min-height: 44px;
            font-size: 16px;
        }
        
        /* Optimize sidebar for mobile */
        .css-1d391kg {
            width: 100%;
        }
        
        /* Hide complex charts on mobile */
        .plotly-graph-div {
            height: 300px !important;
        }
    }
    
    /* Tablet optimizations */
    @media screen and (min-width: 769px) and (max-width: 1024px) {
        .main .block-container {
            padding: 2rem;
        }
        
        .stMetric {
            margin: 1rem 0;
        }
    }
    
    /* Desktop optimizations */
    @media screen and (min-width: 1025px) {
        .main .block-container {
            padding: 3rem;
        }
    }
</style>
""", unsafe_allow_html=True)
```

## Mobile-Specific Features

### 1. Responsive Layout
- Use `st.columns()` with responsive breakpoints
- Stack elements vertically on mobile
- Optimize table display for small screens

### 2. Touch-Friendly Controls
- Larger buttons (min 44px height)
- Increased spacing between interactive elements
- Swipe-friendly navigation

### 3. Performance Optimizations
- Lazy loading of charts
- Reduced data fetching on mobile
- Optimized image sizes

### 4. Mobile Navigation
- Collapsible sidebar
- Bottom navigation bar
- Quick access to key features

## Implementation Steps

1. **Update Streamlit config** (already done)
2. **Add mobile CSS** to dashboard
3. **Test on mobile devices**
4. **Optimize performance**
5. **Add mobile-specific features**

## Testing Checklist

- [ ] Test on iPhone (Safari)
- [ ] Test on Android (Chrome)
- [ ] Test on tablet (iPad/Android)
- [ ] Verify touch interactions
- [ ] Check loading performance
- [ ] Test offline capabilities
- [ ] Verify responsive design
