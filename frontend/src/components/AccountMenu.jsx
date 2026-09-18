import { useState, useRef, useEffect } from "react";
import { ChevronDown, LogOut } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import "./AccountMenu.css";

export default function AccountMenu() {
  const { currentUser, currentRole, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    
    function handleEscape(event) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }
    
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleEscape);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  if (!currentUser || !currentRole) return null;

  const initial = currentUser.name ? currentUser.name.trim().charAt(0).toUpperCase() : "?";
  
  const formatRole = (roleStr) => {
    return roleStr
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  };

  const formattedRole = formatRole(currentRole);

  const handleSignOut = () => {
    setIsOpen(false);
    logout();
  };

  return (
    <div className="account-menu-container" ref={menuRef}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="account-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        <div className="account-menu-avatar">
          {initial}
          <div className="account-menu-status-dot" />
        </div>
        
        <div className="account-menu-info">
          <span className="account-menu-name">{currentUser.name}</span>
          <span className="account-menu-role">{formattedRole}</span>
        </div>
        
        <ChevronDown size={16} className="account-menu-chevron" />
      </button>

      {isOpen && (
        <div 
          className="account-menu-dropdown" 
          role="menu"
        >
          <div className="account-menu-header">
            <div className="account-menu-avatar-lg">
              {initial}
            </div>
            <div className="account-menu-header-info">
              <span className="account-menu-header-name">{currentUser.name}</span>
              <span className="account-menu-header-email">{currentUser.email}</span>
              <span className="account-menu-header-role">{formattedRole}</span>
            </div>
          </div>
          
          <div className="account-menu-divider" />
          
          <div className="account-menu-actions">
            <button 
              className="account-menu-action-item" 
              role="menuitem"
              onClick={handleSignOut}
            >
              <div className="account-menu-action-icon">
                <LogOut size={16} />
              </div>
              <div className="account-menu-action-text">
                <span className="account-menu-action-title">Sign out</span>
                <span className="account-menu-action-desc">Sign out of this session</span>
              </div>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
