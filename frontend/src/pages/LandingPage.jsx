import React, { useState } from 'react';
import './LandingPage.css';

// Simple accordion component for FAQ
function FaqItem({ question, answer }) {
  const [isOpen, setIsOpen] = useState(false);
  
  return (
    <div className="landing-faq-item">
      <button 
        className="landing-faq-question" 
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span>{question}</span>
        <span>{isOpen ? '−' : '+'}</span>
      </button>
      {isOpen && <div className="landing-faq-answer">{answer}</div>}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="landing-page">
      {/* 1. TOP NAVIGATION */}
      <nav className="landing-nav">
        <div className="landing-container">
          <div className="landing-brand">
            <div className="landing-brand-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
              </svg>
            </div>
            Servora
          </div>
          <div className="landing-nav-links">
            <a href="#how-it-works">How it works</a>
            <a href="#features">Features</a>
            <a href="#resources">Resources</a>
          </div>
          <div className="landing-nav-actions">
            <a href="https://github.com/Deekshith2205/Servora" target="_blank" rel="noreferrer" aria-label="GitHub">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>
            </a>
            <a href="/app" className="landing-btn-primary">Open live demo &rarr;</a>
          </div>
        </div>
      </nav>

      {/* 2. HERO */}
      <section className="landing-hero">
        <div className="landing-container landing-hero-grid">
          <div>
            <span className="landing-eyebrow">Autonomous Customer Support</span>
            <h1>Support that investigates, resolves, and knows when to hand off.</h1>
            <p>
              Servora is an autonomous customer-support system built around context retention, reasoning, automation, and human handoff.
            </p>
            <div className="landing-hero-actions">
              <a href="/app" className="landing-btn-primary">Try the live demo &rarr;</a>
              <a href="https://github.com/Deekshith2205/Servora/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer" className="landing-btn-secondary">View architecture &#8599;</a>
            </div>
          </div>
          <div className="landing-hero-preview">
            <img src="/assets/chat-preview.png" alt="Servora Customer Chat showing autonomous tool execution trace" />
          </div>
        </div>
      </section>

      {/* 3. FOUR CORE PILLARS */}
      <div className="landing-pillars">
        <div className="landing-container landing-pillars-grid">
          <div className="landing-pillar">
            <div className="landing-pillar-icon">&#9776;</div>
            <div className="landing-pillar-content">
              <h4>Context retention</h4>
              <p>Maintains customer context across conversations.</p>
            </div>
          </div>
          <div className="landing-pillar">
            <div className="landing-pillar-icon">&#9881;</div>
            <div className="landing-pillar-content">
              <h4>Reasoning</h4>
              <p>Understands intent and plans the appropriate approach.</p>
            </div>
          </div>
          <div className="landing-pillar">
            <div className="landing-pillar-icon">&#9889;</div>
            <div className="landing-pillar-content">
              <h4>Automation</h4>
              <p>Investigates, uses tools, and takes action where possible.</p>
            </div>
          </div>
          <div className="landing-pillar">
            <div className="landing-pillar-icon">&#128101;</div>
            <div className="landing-pillar-content">
              <h4>Human handoff</h4>
              <p>Escalates complex cases with the investigation context.</p>
            </div>
          </div>
        </div>
      </div>

      {/* 4. THE PROBLEM / SERVORA DIFFERENCE */}
      <section id="how-it-works" className="landing-section">
        <div className="landing-container landing-problem">
          <h2 className="landing-problem-title">
            Most support systems stop at categorizing a ticket.<br/>
            <span className="landing-problem-highlight">Servora investigates it.</span>
          </h2>
          <p className="landing-section-subtitle" style={{margin: '0 auto 4rem'}}>
            From understanding intent to taking action and verifying results, Servora follows a structured agent pipeline designed for real customer support &mdash; with human handoff when needed.
          </p>
          
          <div className="landing-pipeline">
            <div className="landing-pipeline-step">
              <div className="landing-pipeline-icon">&#128269;</div>
              <div>
                <h4 style={{margin: 0}}>Classify</h4>
                <p style={{fontSize: '0.85rem', color: 'var(--landing-text-secondary)', margin: 0}}>Understand intent</p>
              </div>
            </div>
            <div className="landing-pipeline-arrow">&rarr;</div>
            <div className="landing-pipeline-step">
              <div className="landing-pipeline-icon">&#128196;</div>
              <div>
                <h4 style={{margin: 0}}>Plan</h4>
                <p style={{fontSize: '0.85rem', color: 'var(--landing-text-secondary)', margin: 0}}>Create approach</p>
              </div>
            </div>
            <div className="landing-pipeline-arrow">&rarr;</div>
            <div className="landing-pipeline-step">
              <div className="landing-pipeline-icon">&#9881;</div>
              <div>
                <h4 style={{margin: 0}}>Investigate</h4>
                <p style={{fontSize: '0.85rem', color: 'var(--landing-text-secondary)', margin: 0}}>Use tools and data</p>
              </div>
            </div>
            <div className="landing-pipeline-arrow">&rarr;</div>
            <div className="landing-pipeline-step">
              <div className="landing-pipeline-icon">&#10003;</div>
              <div>
                <h4 style={{margin: 0}}>Verify</h4>
                <p style={{fontSize: '0.85rem', color: 'var(--landing-text-secondary)', margin: 0}}>Check results</p>
              </div>
            </div>
            <div className="landing-pipeline-arrow">&rarr;</div>
            <div className="landing-pipeline-step">
              <div className="landing-pipeline-icon" style={{color: '#10b981'}}>&#10004;</div>
              <div>
                <h4 style={{margin: 0}}>Resolve</h4>
                <p style={{fontSize: '0.85rem', color: 'var(--landing-text-secondary)', margin: 0}}>Answer or escalate</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4.5 3-COLUMN FEATURE SECTION */}
      <section className="landing-section" style={{paddingTop: 0}}>
        <div className="landing-container">
          <span className="landing-eyebrow">Features</span>
          <h2 className="landing-section-title">A complete support pipeline</h2>
          <div className="landing-resources-grid" style={{gridTemplateColumns: 'repeat(3, 1fr)', marginTop: '2rem'}}>
            <div className="landing-resource-card" style={{cursor: 'default'}}>
              <h3 style={{fontSize: '1.25rem', marginBottom: '1rem'}}>Understand</h3>
              <ul style={{paddingLeft: '1.25rem', color: 'var(--landing-text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.95rem'}}>
                <li>Customer context</li>
                <li>Intent classification</li>
                <li>Conversation history</li>
              </ul>
            </div>
            <div className="landing-resource-card" style={{cursor: 'default'}}>
              <h3 style={{fontSize: '1.25rem', marginBottom: '1rem'}}>Investigate</h3>
              <ul style={{paddingLeft: '1.25rem', color: 'var(--landing-text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.95rem'}}>
                <li>Specialist agents</li>
                <li>Real tool calling</li>
                <li>Database reasoning</li>
              </ul>
            </div>
            <div className="landing-resource-card" style={{cursor: 'default'}}>
              <h3 style={{fontSize: '1.25rem', marginBottom: '1rem'}}>Resolve or Escalate</h3>
              <ul style={{paddingLeft: '1.25rem', color: 'var(--landing-text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.95rem'}}>
                <li>Verified answers</li>
                <li>Actions where supported</li>
                <li>Human handoff with context</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* 5. PRODUCT UI SHOWCASE */}
      <section id="features" className="landing-section" style={{background: 'var(--landing-surface-blue)'}}>
        <div className="landing-container landing-values-grid">
          <div className="landing-value-card">
            <span className="landing-value-eyebrow">For your customers</span>
            <h3>One conversation. Real answers.</h3>
            <p>Servora retains context and investigates across available customer data to find the right answer, avoiding repeated questions.</p>
            <div className="landing-value-image">
              <img src="/assets/chat-preview.png" alt="Customer chat showing context retention and tool usage" />
            </div>
          </div>
          <div className="landing-value-card">
            <span className="landing-value-eyebrow">For your support team</span>
            <h3>Escalations with full context.</h3>
            <p>When Servora escalates a case, the support team receives the context available from the investigation&mdash;category, sentiment, urgency, and trace.</p>
            <div className="landing-value-image">
              <img src="/assets/dashboard-preview.png" alt="Staff dashboard showing escalation queue" />
            </div>
          </div>
        </div>
      </section>

      {/* 6. RESOURCES GRID */}
      <section id="resources" className="landing-section">
        <div className="landing-container">
          <span className="landing-eyebrow">Resources</span>
          <h2 className="landing-section-title">Learn more about Servora</h2>
          <div className="landing-resources-grid">
            <a href="https://github.com/Deekshith2205/Servora" target="_blank" rel="noreferrer" className="landing-resource-card">
              <h4>GitHub Repository</h4>
              <p>View the source code</p>
            </a>
            <a href="https://github.com/Deekshith2205/Servora/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer" className="landing-resource-card">
              <h4>Architecture</h4>
              <p>System design and architecture</p>
            </a>
            <a href="https://github.com/Deekshith2205/Servora/issues" target="_blank" rel="noreferrer" className="landing-resource-card">
              <h4>Issues & Roadmap</h4>
              <p>See what's next</p>
            </a>
            <a href="https://github.com/Deekshith2205/Servora/blob/main/CONTRIBUTING.md" target="_blank" rel="noreferrer" className="landing-resource-card">
              <h4>Contributing Guide</h4>
              <p>Get involved</p>
            </a>
          </div>
        </div>
      </section>

      {/* 7. FAQ */}
      <section className="landing-section" style={{paddingTop: 0}}>
        <div className="landing-container">
          <span className="landing-eyebrow">FAQ</span>
          <h2 className="landing-section-title">Common questions</h2>
          <div className="landing-faq-list">
            <FaqItem 
              question="What is Servora?" 
              answer="Servora is an autonomous customer-support system that understands intent, investigates across data sources, takes real actions where supported, and escalates to a human with full context." 
            />
            <FaqItem 
              question="How does Servora investigate customer requests?" 
              answer="Incoming messages flow through a pipeline: a Classifier extracts intent, a Planner creates a strategy, and Specialist agents use real database tools to ground their answers in facts." 
            />
            <FaqItem 
              question="What happens when Servora cannot resolve a request?" 
              answer="The system prepares a structured escalation packet containing the situation, attempted fixes, and a recommendation, which appears on the Staff Dashboard for human review." 
            />
            <FaqItem 
              question="Can I try the application?" 
              answer="Yes, click 'Open live demo' to interact with the current implementation. Note that it currently uses seeded demo data to illustrate the core reasoning concepts." 
            />
          </div>
        </div>
      </section>

      {/* 8. FINAL CTA */}
      <div className="landing-container">
        <div className="landing-final-cta">
          <h2 style={{fontSize: '2.5rem', marginBottom: '1rem'}}>Ready to see it in action?</h2>
          <p style={{color: 'var(--landing-text-secondary)', fontSize: '1.2rem', marginBottom: '2.5rem'}}>
            Try the live demo and experience autonomous customer support.
          </p>
          <div className="landing-hero-actions" style={{justifyContent: 'center'}}>
            <a href="/app" className="landing-btn-primary">Open live demo &rarr;</a>
            <a href="https://github.com/Deekshith2205/Servora/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer" className="landing-btn-secondary">Read the architecture &#8599;</a>
          </div>
        </div>
      </div>

      {/* 9. FOOTER */}
      <footer className="landing-footer">
        <div className="landing-container">
          <div className="landing-footer-grid">
            <div>
              <div className="landing-brand" style={{marginBottom: '0.5rem'}}>
                <div className="landing-brand-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                  </svg>
                </div>
                Servora
              </div>
              <p style={{color: 'var(--landing-text-secondary)', maxWidth: '300px'}}>
                Autonomous customer support with reasoning, automation, context, and human handoff.
              </p>
            </div>
            <div className="landing-footer-links">
              <a href="https://github.com/Deekshith2205/Servora" target="_blank" rel="noreferrer">GitHub</a>
              <a href="https://github.com/Deekshith2205/Servora/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer">Architecture</a>
              <a href="https://github.com/Deekshith2205/Servora/issues" target="_blank" rel="noreferrer">Issues</a>
              <a href="https://github.com/Deekshith2205/Servora/blob/main/CONTRIBUTING.md" target="_blank" rel="noreferrer">Contributing</a>
            </div>
          </div>
          <div className="landing-footer-bottom">
            <span>Built for the Customer Support track.</span>
            <span>&copy; {new Date().getFullYear()} Servora Contributors</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
