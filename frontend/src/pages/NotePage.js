import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ReactComponent as ArrowLeft } from '../assets/arrow-left.svg'

const NotePage = () => {
  const { id } = useParams()
  const navigate = useNavigate()
  const [note, setNote] = useState({})

  useEffect(() => {
    const getNote = async () => {
      if (id === 'new') return
      const response = await fetch(`/api/notes/${id}`)
      const data = await response.json()
      setNote(data)
    }

    getNote()
  }, [id])

  const createNote = async () => {
    await fetch('/api/notes/create/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ...note, updated: new Date() }),
    })
  }

  const updateNote = async () => {
    await fetch(`/api/notes/${id}/update/`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ...note, updated: new Date() }),
    })
  }

  const deleteNote = async () => {
    await fetch(`/api/notes/${id}/delete/`, {
      method: 'DELETE',
    })
    navigate('/')
  }

  const handleSubmit = () => {
    if (id !== 'new' && !note.body) {
      deleteNote()
    } else if (id !== 'new') {
      updateNote()
    } else if (id === 'new' && note !== null) {
      createNote()
    }
    navigate('/')
  }

  return (
    <div className='note'>
      <div className='note-header'>
        <h3 className='note-back'>
          <Link to='/'>
            <ArrowLeft onClick={handleSubmit} />
            <span>Back</span>
          </Link>
        </h3>
        <div className='note-actions'>
          {id !== 'new' ? (
            <button className='note-action note-action-delete' onClick={deleteNote}>Delete</button>
          ) : (
            <button className='note-action note-action-save' onClick={handleSubmit}>Save</button>
          )}
        </div>
      </div>
      <div className='note-intro'>
        <p className='note-kicker'>{id === 'new' ? 'New entry' : 'Editing note'}</p>
        <h2>{id === 'new' ? 'Write something worth keeping' : 'Refine your note'}</h2>
      </div>
      <div className='note-body'>
        <textarea
          placeholder='Start with a title, then write your note here...'
          onChange={(event) => { setNote({ ...note, body: event.target.value }) }}
          value={note.body || ''}
        />
      </div>
    </div>
  )
}

export default NotePage
