import React from 'react'
import { Link } from 'react-router-dom'
import { ReactComponent as Addicon } from '../assets/add.svg'

const AddButton = () => {
  return (
    <Link className='floating-button' to='note/new/'>
      <span>New note</span>
      <Addicon />
    </Link>
  )
}

export default AddButton
