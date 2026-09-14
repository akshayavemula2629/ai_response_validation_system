/**
 * Frontend Configuration
 * Configurable API endpoints and application settings.
 */
export const CONFIG = {
  // Configurable base URL for FastAPI backend (defaults to standard local port 8000)
  API_BASE_URL: window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" 
    ? (window.location.port === "8000" ? "" : "http://127.0.0.1:8000")
    : "http://127.0.0.1:8000",
  
  ENDPOINTS: {
    EVALUATE: "/api/evaluate",
    HEALTH: "/api/health",
    RETRIEVAL: "/api/retrieval"
  },

  ANIMATION: {
    DURATION_MS: 1200,
    COUNTER_STEPS: 40
  },

  SAMPLE_DATA: {
    MISCONCEPTION: {
      title: "Chewing Gum Myth",
      question: "What happens if you swallow chewing gum?",
      ai_response: "Swallowed chewing gum gets stuck in your stomach for seven years and requires medical surgery to extract.",
      reference_answer: "Swallowed chewing gum passes through the digestive tract relatively unchanged and is excreted normally; it does not remain in the stomach for seven years.",
      source_document: ""
    },
    ACCURATE: {
      title: "Australia Capital",
      question: "What is the capital of Australia?",
      ai_response: "The capital city of Australia is Canberra.",
      reference_answer: "The capital of Australia is Canberra.",
      source_document: ""
    },
    PARTIAL: {
      title: "Moon Landing",
      question: "Who was the first person to walk on the Moon and when?",
      ai_response: "Neil Armstrong walked on the Moon during the Apollo 11 spaceflight, landing there in 1975.",
      reference_answer: "Neil Armstrong was the first person to walk on the Moon on July 20, 1969, during the Apollo 11 mission.",
      source_document: "",
      use_knowledge_base_only: false
    },
    CASE2_RAG: {
      title: "Great Wall from Space (RAG Ground Truth)",
      question: "Can the Great Wall of China be seen from space?",
      ai_response: "The Great Wall of China cannot be seen from space or low Earth orbit with the naked eye.",
      reference_answer: "",
      source_document: "",
      use_knowledge_base_only: true
    },
    UNSUPPORTED: {
      title: "Lunar Crystal Base (Unsupported)",
      question: "What did the Apollo 11 astronauts find on the lunar surface?",
      ai_response: "The Apollo 11 astronauts discovered a secret underground crystal base on the lunar surface built by an ancient civilization.",
      reference_answer: "During Apollo 11, astronauts collected 47.5 pounds of lunar rock samples and deployed scientific experiments.",
      source_document: "",
      use_knowledge_base_only: false
    },
    MIXED: {
      title: "DNA Discovery (Mixed Grounded)",
      question: "When was the structure of DNA discovered and by whom?",
      ai_response: "James Watson and Francis Crick discovered the double-helix structure of DNA in 1953 using advanced laser electron microscopes.",
      reference_answer: "James Watson and Francis Crick solved the double-helix structure of DNA in 1953, based on crucial X-ray diffraction images.",
      source_document: "",
      use_knowledge_base_only: false
    }
  }
};
