import React, { useState } from 'react';
import './LandingPage.css';

// Simple accordion component for FAQ
function FaqItem({ question, answer }) {
  const [isOpen, setIsOpen] = useState(false);
  
  return (
    <div className="faq-item">
      <button className="faq-question" onClick={() => setIsOpen(!isOpen)}>
        <span>{question}</span>
        <span>{isOpen ? '−' : '+'}</span>
      </button>
      {isOpen && <div className="faq-answer">{answer}</div>}
    </div>
  );
}

export default function LandingPage() {
  const [activeTab, setActiveTab] = useState('understand');

  return (
    <div className="landing-page">
      {/* 1. TOP NAVIGATION */}
      <nav className="landing-nav">
        <div className="container">
          <div className="brand">
            <div className="brand-icon"></div>
            Servora
          </div>
          <div className="nav-links">
            <a href="#how-it-works">How it works</a>
            <a href="#features">Features</a>
            <a href="#resources">Resources</a>
          </div>
          <div className="nav-actions">
            <a href="/app" className="btn-primary">Open live demo</a>
          </div>
        </div>
      </nav>

      {/* 2. HERO */}
      <section className="section hero">
        <div className="hero-glow"></div>
        <div className="container">
          <h1>Support that investigates, resolves, and knows when to hand off.</h1>
          <p className="hero-subtitle">
            An autonomous customer-support system built around context retention, reasoning, automation, and human handoff.
          </p>
          <div className="hero-actions">
            <a href="/app" className="btn-primary">Try the live demo</a>
            <a href="https://github.com/Deekshith2205/Servora/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer" className="btn-secondary">View the architecture</a>
          </div>

          {/* Product Preview */}
          <div className="hero-screenshot-container">
            <img 
              src="/assets/chat-preview.png" 
              alt="Servora Customer Chat interface showing autonomous investigation" 
              className="product-screenshot"
            />
          </div>
        </div>
      </section>

      {/* 3. TRUST / POSITIONING STRIP */}
      <div className="pillar-strip">
        <div className="container pillar-content">
          <span>Context</span>
          <span>·</span>
          <span>Reasoning</span>
          <span>·</span>
          <span>Automation</span>
          <span>·</span>
          <span>Human handoff</span>
        </div>
      </div>

      {/* 4. NARRATIVE / PROBLEM SECTION */}
      <section id="how-it-works" className="section">
        <div className="container split-layout">
          <div>
            <h2>Most support systems stop at categorizing a ticket. <span className="text-gradient">Servora investigates it.</span></h2>
            <p>
              Servora runs a continuous reasoning pipeline: it classifies intent, investigates with tools, 
              takes action where appropriate, verifies the result, and preserves context.
            </p>
            <p>
              If a case is too complex, it escalates smoothly—providing a structured handoff packet to a human agent on the Staff Dashboard.
            </p>
          </div>
          <div className="architecture-diagram">
            <div className="arch-node">Customer Message</div>
            <div className="arch-arrow">↓</div>
            <div className="arch-node">Classifier Agent</div>
            <div className="arch-arrow">↓</div>
            <div className="arch-node">Planner Agent</div>
            <div className="arch-arrow">↓</div>
            <div className="arch-node accent">Specialist Agents (Tools)</div>
            <div className="arch-arrow">↓</div>
            <div className="arch-node">Verification Agent</div>
            <div className="arch-arrow">↓</div>
            <div className="arch-node">Resolved OR Escalated</div>
          </div>
        </div>
      </section>

      {/* 5. IMPACT / REAL PROJECT STATS */}
      <div className="pillar-strip">
        <div className="container pillar-content">
          <span>4 Specialist domains</span>
          <span>1 Tool-grounded support pipeline</span>
          <span>Human handoff with full context</span>
        </div>
      </div>

      {/* 6. FEATURE SHOWCASE WITH TABS */}
      <section id="features" className="section">
        <div className="container">
          <div className="section-title">Explore the pipeline</div>
          <div className="section-subtitle">See how Servora breaks down complex interactions.</div>
          
          <div className="tabs-container">
            <div className="tabs-nav">
              <button className={`tab-btn ${activeTab === 'understand' ? 'active' : ''}`} onClick={() => setActiveTab('understand')}>Understand</button>
              <button className={`tab-btn ${activeTab === 'resolve' ? 'active' : ''}`} onClick={() => setActiveTab('resolve')}>Resolve</button>
              <button className={`tab-btn ${activeTab === 'escalate' ? 'active' : ''}`} onClick={() => setActiveTab('escalate')}>Escalate</button>
            </div>
            
            <div className="tab-content">
              {activeTab === 'understand' && (
                <>
                  <div>
                    <h3>Classifier</h3>
                    <p>Analyzes incoming messages to extract category, sentiment, and true urgency.</p>
                    <ul>
                      <li>Determines emotional tone</li>
                      <li>Extracts domain (billing, technical, etc.)</li>
                      <li>Provides clear reasoning for its score</li>
                    </ul>
                  </div>
                  <div className="tab-image-container">
                    <img src="/assets/chat-preview.png" alt="Customer chat showing intent analysis" className="tab-screenshot" />
                  </div>
                </>
              )}
              {activeTab === 'resolve' && (
                <>
                  <div>
                    <h3>Specialist Agents</h3>
                    <p>Grounds factual claims through tools before answering.</p>
                    <ul>
                      <li>Never answers from model memory alone</li>
                      <li>Calls real database functions</li>
                      <li>Can take action (e.g. issue refund)</li>
                    </ul>
                  </div>
                  <div className="tab-image-container">
                    <img src="/assets/chat-preview.png" alt="Customer chat showing tool execution trace" className="tab-screenshot" />
                  </div>
                </>
              )}
              {activeTab === 'escalate' && (
                <>
                  <div>
                    <h3>Human Handoff</h3>
                    <p>When unable to resolve, prepares a structured handoff for the Staff Dashboard.</p>
                    <ul>
                      <li>Summarizes situation</li>
                      <li>Lists attempted fixes</li>
                      <li>Proposes root-cause hypothesis</li>
                    </ul>
                  </div>
                  <div className="tab-image-container">
                    <img src="/assets/dashboard-preview.png" alt="Staff dashboard showing escalation context" className="tab-screenshot" />
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* 7. TWO-COLUMN VALUE SECTION */}
      <section className="section">
        <div className="container values-grid">
          <div className="value-card">
            <div className="value-image">
              <img src="/assets/chat-preview.png" alt="Customer chat" />
            </div>
            <h3>For your customers</h3>
            <p>One coherent conversation. Context is retained, investigation replaces repeated questioning, and resolutions happen instantly when possible.</p>
          </div>
          <div className="value-card">
            <div className="value-image">
              <img src="/assets/dashboard-preview.png" alt="Staff dashboard" />
            </div>
            <h3>For your support team</h3>
            <p>Escalations arrive with rich context. Staff members instantly see category, sentiment, urgency, and prior troubleshooting steps. No cold transfers.</p>
          </div>
        </div>
      </section>

      {/* 9. RESOURCES GRID */}
      <section id="resources" className="section">
        <div className="container">
          <h2 className="section-title">Resources</h2>
          <div className="resources-grid">
            <a href="https://github.com/Deekshith2205/Servora" target="_blank" rel="noreferrer" className="resource-card">
              <h4>GitHub Repository</h4>
              <p>View the source code</p>
            </a>
            <a href="https://github.com/Deekshith2205/Servora/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer" className="resource-card">
              <h4>Architecture</h4>
              <p>Read the system design</p>
            </a>
            <a href="https://github.com/Deekshith2205/Servora/issues" target="_blank" rel="noreferrer" className="resource-card">
              <h4>Issues & Roadmap</h4>
              <p>See what's next</p>
            </a>
            <a href="https://github.com/Deekshith2205/Servora/blob/main/CONTRIBUTING.md" target="_blank" rel="noreferrer" className="resource-card">
              <h4>Contributing Guide</h4>
              <p>Learn how to deploy locally</p>
            </a>
          </div>
        </div>
      </section>

      {/* 10. FAQ ACCORDION */}
      <section className="section">
        <div className="container">
          <h2 className="section-title">Frequently Asked Questions</h2>
          <div className="faq-list">
            <FaqItem 
              question="What is Servora?" 
              answer="Servora is an autonomous customer-support system that understands intent, investigates across data sources, takes real actions, and escalates to a human with full context." 
            />
            <FaqItem 
              question="What does the agent pipeline do?" 
              answer="It moves incoming messages through a multi-stage flow: Classifier -> Planner -> Specialist Agents -> Verification -> Memory -> Resolution or Escalation." 
            />
            <FaqItem 
              question="What LLM powers Servora?" 
              answer="The current implementation defaults to Anthropic's Claude models, wrapped in a generic LLM layer that can be swapped out." 
            />
            <FaqItem 
              question="Does Servora use real customer data?" 
              answer="The application currently uses seeded demo data (e.g., Customer ID 1) to demonstrate the logic. Real customer auth is not yet implemented." 
            />
            <FaqItem 
              question="How does the human handoff work?" 
              answer="When the system cannot resolve an issue, the Escalation Agent prepares a structured packet containing the situation, attempted fixes, and a recommendation, which appears on the Staff Dashboard." 
            />
          </div>
        </div>
      </section>

      {/* 11. FINAL CTA */}
      <section className="final-cta">
        <div className="container">
          <h2>See Servora work on a real support conversation.</h2>
          <div className="hero-actions" style={{ marginBottom: 0 }}>
            <a href="/app" className="btn-primary">Open live demo</a>
            <a href="https://github.com/Deekshith2205/Servora/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer" className="btn-secondary">Read the architecture</a>
          </div>
        </div>
      </section>

      {/* 12. FOOTER */}
      <footer className="footer">
        <div className="container">
          <div className="footer-grid">
            <div className="footer-brand">
              <div className="brand" style={{ fontSize: '1.25rem' }}>Servora</div>
              <p>Built for the Customer Support hackathon track.</p>
            </div>
            <div className="footer-links">
              <a href="https://github.com/Deekshith2205/Servora" target="_blank" rel="noreferrer">GitHub</a>
              <a href="https://github.com/Deekshith2205/Servora/blob/main/docs/ARCHITECTURE.md" target="_blank" rel="noreferrer">Architecture</a>
              <a href="https://github.com/Deekshith2205/Servora/issues" target="_blank" rel="noreferrer">Issues</a>
              <a href="https://github.com/Deekshith2205/Servora/blob/main/CONTRIBUTING.md" target="_blank" rel="noreferrer">Contributing</a>
            </div>
          </div>
          <div className="footer-bottom">
            &copy; {new Date().getFullYear()} Servora Contributors
          </div>
        </div>
      </footer>
    </div>
  );
}
