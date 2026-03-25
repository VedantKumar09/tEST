import React from 'react';
import Editor from '@monaco-editor/react';

const CodeEditor = ({ code, setCode, language, setLanguage, onRun, running, output, executionTime }) => {
  return (
    <div className="coding-editor-panel">
      <div className="editor-header">
        <div className="editor-actions">
          <select 
            value={language} 
            onChange={(e) => setLanguage(e.target.value)}
            className="form-input"
            style={{ padding: '4px 8px', fontSize: '12px', width: 'auto' }}
          >
            <option value="python">Python</option>
            <option value="c">C</option>
            <option value="java">Java</option>
            <option value="sql">SQL</option>
          </select>
          <span className="editor-lang-badge">{language.toUpperCase()}</span>
        </div>
        <button 
          className={`btn ${running ? 'btn-secondary' : 'btn-primary'}`}
          onClick={onRun}
          disabled={running}
          style={{ padding: '4px 12px', fontSize: '12px' }}
        >
          {running ? 'Running...' : 'Run Code'}
        </button>
      </div>

      <div className="monaco-wrapper">
        <Editor
          height="100%"
          language={language}
          theme="vs-dark"
          value={code}
          onChange={(val) => setCode(val)}
          onMount={(editor, monaco) => {
            editor.onKeyDown((e) => {
              if ((e.ctrlKey || e.metaKey) && e.keyCode === monaco.KeyCode.KeyV) {
                e.preventDefault();
                e.stopPropagation();
              }
            });
            editor.updateOptions({ contextmenu: false });
          }}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            scrollBeyondLastLine: false,
            padding: { top: 16 }
          }}
        />
      </div>

      {output !== null && (
        <div className="output-console">
          <div className="output-header">
            <span>Execution Output {executionTime && <span className="exec-time">{executionTime}</span>}</span>
          </div>
          <pre className="output-content">{output}</pre>
        </div>
      )}
    </div>
  );
};

export default CodeEditor;
