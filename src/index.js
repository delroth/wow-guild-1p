import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';
import './index.css';

function urlFragmentChanged() {
  var fragment = window.location.hash.replace(/^#/, '');
  ReactDOM.render(
    <App fragment={fragment} />,
    document.getElementById('root')
  );
}

window.addEventListener('hashchange', urlFragmentChanged);
urlFragmentChanged();
