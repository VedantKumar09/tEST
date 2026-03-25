import React from 'react';

const QuestionDisplay = ({ question, stdin, setStdin }) => {
  if (!question) return null;

  return (
    <div className="coding-question-panel">
      <div className="badge badge-info">{question.difficulty}</div>
      <h3 className="coding-title">{question.title}</h3>
      <div className="coding-description">
        {question.description}
      </div>
      <hr style={{ borderColor: 'var(--border)', margin: '20px 0' }} />
      <div className="stdin-section">
        <label className="stdin-label">Custom Input (stdin)</label>
        <textarea
          className="stdin-textarea"
          rows={3}
          placeholder="Enter input for your program here..."
          value={stdin}
          onChange={(e) => setStdin(e.target.value)}
        />
      </div>
    </div>
  );
};

export default QuestionDisplay;
