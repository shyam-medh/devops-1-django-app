import React, { useState,useEffect } from 'react'
import ListItem from '../components/ListItem.js'
import AddButton from '../components/AddButton.js'

const NotesListPage = () => {
    let [notes, setNote] = useState([])

    useEffect(() => {
        getNotes()
    }, []) // fires once when the component is mounted

    let getNotes = async () => {
        let response = await fetch('/api/notes/')
        let data = await response.json()
        setNote(data)
    }

    return (
        <div className='notes'>
            <div className="notes-header">
                <div>
                    <p className="notes-kicker">Overview</p>
                    <h2 className="notes-title">Your notes</h2>
                </div>
                <div className="notes-count-wrap">
                    <p className="notes-count">{notes.length}</p>
                    <span>saved</span>
                </div>
            </div>
            {notes.length ? (
                <div className='notes-list'>
                    {notes.map((note,index) => {
                        return (
                            <div className='note-preview' key={index}>
                                <ListItem note={note}/>
                            </div>
                        )
                    })}
                </div>
            ) : (
                <div className='notes-empty'>
                    <p className='notes-empty-kicker'>No notes yet</p>
                    <h3>Start your first entry</h3>
                    <p>Use the button below to create a note for ideas, reminders, or quick drafts.</p>
                </div>
            )}
            <AddButton/>
        </div>
    )
}

export default NotesListPage
