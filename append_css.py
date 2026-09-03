with open("web/style.css", "a", encoding="utf-8") as f:
    f.write("""
/* Diagnostics Center Styles */
.diagnostics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: var(--space-md);
    margin-bottom: var(--space-lg);
}

.diagnostics-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: var(--radius-md);
    padding: var(--space-md);
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: all 0.2s ease;
}

.diagnostics-card:hover {
    border-color: rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.05);
}

.diag-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    font-size: 1rem;
}

.diag-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 12px;
}

.diag-status.HEALTHY { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.diag-status.DEGRADED { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.diag-status.OFFLINE { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.diag-status.ERROR { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.diag-status.UNKNOWN { background: rgba(168, 85, 247, 0.15); color: #c084fc; }

.diag-details {
    font-size: 0.8rem;
    color: var(--text-secondary);
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.diag-event {
    margin-top: 4px;
    font-size: 0.85rem;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.timeline-item {
    padding: 8px 12px;
    border-left: 2px solid rgba(255,255,255,0.1);
    margin-left: 8px;
    position: relative;
    font-size: 0.85rem;
}

.timeline-item::before {
    content: '';
    position: absolute;
    left: -5px;
    top: 12px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-secondary);
}

.timeline-time {
    color: var(--text-secondary);
    font-size: 0.75rem;
    margin-bottom: 2px;
}

.error-item {
    background: rgba(239, 68, 68, 0.05);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: var(--radius-sm);
    padding: 10px;
    margin-bottom: 8px;
    font-size: 0.85rem;
}

.error-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 4px;
}

.error-type {
    font-weight: 600;
    color: #f87171;
}

.error-count {
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
    font-size: 0.7rem;
    padding: 2px 6px;
    border-radius: 10px;
    font-weight: bold;
}
""")
